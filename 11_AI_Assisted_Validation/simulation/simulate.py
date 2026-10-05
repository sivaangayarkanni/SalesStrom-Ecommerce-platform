#!/usr/bin/env python3
"""SALESTORM flash-sale simulation (stdlib only).

Safe mode models the layered design:
  L1 CDN SOLD_OUT flag -> L2 local "pool empty" flag -> idempotency store ->
  L3 Redis-like token pool (atomic pop/return) -> L4 DB rows (per-row try-lock = SKIP LOCKED,
  UNIQUE(customer)) -> payment (95%/5%) -> outbox -> Order Service (30 s outage) -> capture.
Invariants are checked after every state-changing operation.
--naive: read stock, sleep, write - no locks - to show overselling.
Time is scaled: 1 simulated second = SCALE real seconds.
--resilience: afterwards run resilience_sim.py (retry storm, inbox dedupe, fencing, salted hot key,
singleflight, coordinated omission).
"""
import argparse, json, os, random, threading, time
from collections import Counter

N_UNITS = 100
SCALE = 0.01                # 1 sim-second = 10 ms real
ARRIVAL_WINDOW = 60.0       # users arrive uniformly over 60 sim-s
TTL = 10.0                  # reservation TTL (sim-s)
OUTAGE = (0.0, 30.0)        # Order Service down for the first 30 sim-s of the sale
DUP_RATE, PAY_OK, ABANDON = 0.02, 0.95, 0.02


class SafeSim:
    def __init__(self, users, seed):
        self.users, self.seed = users, seed
        self.l1_sold_out = False                 # CDN edge flag (final)
        self.l2_empty = False                    # local flag: set on empty pool, cleared on release
        self.pool, self.pool_lock = list(range(N_UNITS)), threading.Lock()
        self.rows = [{"state": "AVAILABLE", "owner": None, "exp": 0.0, "released": False}
                     for _ in range(N_UNITS)]
        self.row_locks = [threading.Lock() for _ in range(N_UNITS)]
        self.meta = threading.Lock()             # counters, indexes, payments, orders
        self.cnt = {"AVAILABLE": N_UNITS, "RESERVED": 0, "SOLD": 0}
        self.unique_customer = set()             # UNIQUE(customer) on active reservations/sales
        self.idem = {}                           # Idempotency-Key -> result | IN_PROGRESS
        self.charges, self.captured, self.order_count = Counter(), set(), Counter()
        self.outbox, self.outbox_lock = [], threading.Lock()
        self.stats, self.answers = Counter(), Counter()
        self.violations, self.checks = [], 0
        self.stop = threading.Event()

    def now(self):
        return (time.monotonic() - self.t0) / SCALE

    def stat(self, k, n=1):
        with self.meta:
            self.stats[k] += n

    def answer(self, tier, dup):
        with self.meta:
            self.answers[tier] += 1
            if dup:
                self.stats["dup_answered_" + tier] += 1
        return tier

    def order_service_down(self):
        return OUTAGE[0] <= self.now() < OUTAGE[1]

    def _check_locked(self, where):          # caller holds self.meta
        self.checks += 1
        c = self.cnt
        errs = []
        if c["AVAILABLE"] + c["RESERVED"] + c["SOLD"] != N_UNITS: errs.append("sum!=100")
        if c["SOLD"] > N_UNITS: errs.append("sold>100")
        if min(c.values()) < 0: errs.append("negative")
        if any(v > 1 for v in self.charges.values()): errs.append("customer charged twice")
        if any(self.order_count[p] != 1 for p in self.captured): errs.append("capture w/o exactly 1 order")
        if errs and len(self.violations) < 50:
            self.violations.append((where, errs, dict(c)))

    def _move(self, i, frm, to, where):      # caller holds row lock i
        assert self.rows[i]["state"] == frm
        self.rows[i]["state"] = to
        with self.meta:
            self.cnt[frm] -= 1
            self.cnt[to] += 1
            if self.cnt["SOLD"] == N_UNITS:
                self.l1_sold_out = True          # publish SOLD_OUT to CDN
            self._check_locked(where)

    def _release(self, i, reason):           # caller holds row lock i
        r = self.rows[i]
        cust = r["owner"]
        self._move(i, "RESERVED", "AVAILABLE", reason)
        r["owner"], r["released"] = None, True
        with self.meta:
            self.unique_customer.discard(cust)
            self.stats["released_" + reason] += 1
        with self.pool_lock:                  # unit is free again -> return its token
            self.pool.append(i)
            self.l2_empty = False

    def request(self, cust, key, dup, rng):
        if self.l1_sold_out: return self.answer("L1_cdn_sold_out", dup)   # edge: final NO
        with self.meta:          # idempotency before L2 so a retry gets its ORIGINAL answer
            prev = self.idem.get(key)
            if prev is None: self.idem[key] = "IN_PROGRESS"
        if prev is not None: return self.answer("idempotent_replay", dup)
        if self.l2_empty: res = self.answer("L2_local_flag", dup)
        else: res = self.reserve_and_pay(cust, dup, rng)
        with self.meta:
            self.idem[key] = res
        return res

    def reserve_and_pay(self, cust, dup, rng):
        with self.pool_lock:
            tok = self.pool.pop() if self.pool else None
            if tok is None: self.l2_empty = True
        if tok is None: return self.answer("L3_pool_reject", dup)
        self.answer("reached_db", dup)
        with self.meta:
            if cust in self.unique_customer:
                self.stats["db_unique_reject"] += 1
                bad = True
            else:
                self.unique_customer.add(cust); bad = False
        row, start = None, rng.randrange(N_UNITS)
        for attempt in range(N_UNITS * 50):
            if bad or row is not None: break
            i = (start + attempt) % N_UNITS
            if not self.row_locks[i].acquire(blocking=False):   # SKIP LOCKED
                self.stat("skip_locked")
                continue
            try:
                r = self.rows[i]
                if r["state"] == "AVAILABLE":
                    self._move(i, "AVAILABLE", "RESERVED", "reserve")
                    r["owner"], r["exp"] = cust, self.now() + TTL
                    row = i
            finally:
                self.row_locks[i].release()
        if row is None:
            with self.pool_lock: self.pool.append(tok); self.l2_empty = False
            if not bad:
                with self.meta: self.unique_customer.discard(cust)
            self.stat("db_no_row")
            return "db_reject"
        if rng.random() < ABANDON:            # user walks away; TTL reaper reclaims
            self.stat("abandoned")
            return "abandoned"
        time.sleep(rng.uniform(1, 3) * SCALE)  # payment authorization latency
        ok = rng.random() < PAY_OK
        with self.row_locks[row]:
            r = self.rows[row]
            if r["state"] != "RESERVED" or r["owner"] != cust:
                self.stat("auth_voided_expired"); return "expired"
            if not ok:
                self._release(row, "payment_failed"); return "payment_failed"
            resold = r["released"]
            self._move(row, "RESERVED", "SOLD", "payment_authorized")
        self.stat("sold")
        if resold: self.stat("resold_units")
        self.on_authorized(f"pay-{cust}", cust)
        return "sold"

    def on_authorized(self, pid, cust):
        if self.order_service_down():
            with self.outbox_lock: self.outbox.append((pid, cust))
            self.stat("outboxed_events")
            return
        self.create_order_and_capture(pid, cust, False)

    def create_order_and_capture(self, pid, cust, from_outbox):
        with self.meta:
            if self.order_count[pid] == 0:        # idempotent order creation keyed by payment id
                self.order_count[pid] += 1
                self.stats["orders_created"] += 1
                if from_outbox: self.stats["orders_created_after_outage"] += 1
            self._check_locked("order_created")
            if pid not in self.captured and self.order_count[pid] == 1:   # capture only after order
                self.captured.add(pid)
                self.charges[cust] += 1
            self._check_locked("capture")

    def outbox_consumer(self):
        while not self.stop.is_set():
            with self.outbox_lock: pending = len(self.outbox)
            if pending:
                if self.order_service_down():
                    self.stat("outbox_retry_while_down")
                else:
                    with self.outbox_lock: batch, self.outbox = self.outbox, []
                    for pid, cust in batch: self.create_order_and_capture(pid, cust, True)
            time.sleep(2 * SCALE)

    def reaper(self):
        while not self.stop.is_set():
            for i in range(N_UNITS):
                if self.row_locks[i].acquire(blocking=False):
                    try:
                        r = self.rows[i]
                        if r["state"] == "RESERVED" and r["exp"] < self.now():
                            self._release(i, "ttl_expired")
                    finally:
                        self.row_locks[i].release()
            time.sleep(SCALE)

    def run(self):
        rng = random.Random(self.seed)
        go = threading.Event()
        dups = set(rng.sample(range(self.users), int(self.users * DUP_RATE)))
        def user(cust, delay, dup):
            r = random.Random(self.seed * 100003 + cust * 2 + dup)
            go.wait(); time.sleep(delay * SCALE)
            self.request(cust, f"idem-{cust}", dup, r)
        threads = []
        for c in range(self.users):
            d = rng.uniform(0, ARRIVAL_WINDOW)
            threads.append(threading.Thread(target=user, args=(c, d, False)))
            if c in dups:   # same Idempotency-Key resent shortly after
                threads.append(threading.Thread(target=user, args=(c, d + rng.uniform(0, 0.5), True)))
        for t in threads: t.start()
        self.t0 = time.monotonic()
        bg = [threading.Thread(target=self.outbox_consumer), threading.Thread(target=self.reaper)]
        for t in bg: t.start()
        go.set()
        for t in threads: t.join()
        while True:     # drain: outage over, outbox empty, no live reservations
            with self.outbox_lock: pending = len(self.outbox)
            with self.meta: reserved = self.cnt["RESERVED"]
            if not pending and not reserved and not self.order_service_down(): break
            time.sleep(SCALE)
        self.stop.set()
        for t in bg: t.join()
        with self.meta:      # final full-table scan
            scan = Counter(r["state"] for r in self.rows)
            if dict(scan) != {k: v for k, v in self.cnt.items() if v}:
                self.violations.append(("final_scan", ["row scan != counters"], dict(scan)))
            self._check_locked("final")
        return len(threads), time.monotonic() - self.t0


def run_safe(users, seed):
    s = SafeSim(users, seed)
    nreq, elapsed = s.run()
    st, a = s.stats, s.answers
    dup_total = sum(v for k, v in st.items() if k.startswith("dup_answered_"))
    res = {
        "mode": "safe", "users": users, "requests_total": nreq, "duplicate_requests": int(users * DUP_RATE),
        "elapsed_real_s": round(elapsed, 2),
        "answered_per_tier": {k: a.get(k, 0) for k in
                              ["L1_cdn_sold_out", "L2_local_flag", "L3_pool_reject", "idempotent_replay", "reached_db"]},
        "duplicates_by_tier": {k[len("dup_answered_"):]: v for k, v in st.items() if k.startswith("dup_answered_")},
        "duplicates_collapsed": dup_total - st.get("dup_answered_reached_db", 0),
        "final": dict(s.cnt), "sold": s.cnt["SOLD"],
        "failed_payments": st.get("released_payment_failed", 0),
        "abandoned_ttl_expired": st.get("released_ttl_expired", 0),
        "auth_voided_expired": st.get("auth_voided_expired", 0),
        "resold_units": st.get("resold_units", 0),
        "outboxed_events": st.get("outboxed_events", 0),
        "outbox_retries_while_down": st.get("outbox_retry_while_down", 0),
        "orders_created": st.get("orders_created", 0),
        "orders_created_after_outage": st.get("orders_created_after_outage", 0),
        "captured_payments": len(s.captured),
        "max_charges_per_customer": max(s.charges.values(), default=0),
        "db_unique_rejects": st.get("db_unique_reject", 0), "skip_locked_hits": st.get("skip_locked", 0),
        "invariant_checks": s.checks, "violations": s.violations[:10],
        "invariants": "PASS" if not s.violations and len(s.captured) == s.cnt["SOLD"] else "FAIL",
    }
    assert sum(res["answered_per_tier"].values()) == nreq
    return res


def run_naive(users, seed):
    rng = random.Random(seed)
    stock, sold, go = [N_UNITS], [], threading.Event()
    def buy(c, d):
        go.wait(); time.sleep(d * SCALE)
        s = stock[0]                     # read
        if s > 0:
            time.sleep(0.001)            # "business logic" gap
            stock[0] = s - 1             # write (lost update)
            sold.append(c)
    ts = [threading.Thread(target=buy, args=(c, rng.uniform(0, ARRIVAL_WINDOW))) for c in range(users)]
    for t in ts: t.start()
    t0 = time.monotonic(); go.set()
    for t in ts: t.join()
    n = len(sold)
    return {"mode": "naive", "users": users, "elapsed_real_s": round(time.monotonic() - t0, 2),
            "sold": n, "oversold_by": max(0, n - N_UNITS), "final_stock_counter": stock[0],
            "available_plus_sold": stock[0] + n,
            "invariants": "PASS" if n <= N_UNITS and stock[0] + n == N_UNITS else "FAIL"}


def report(r):
    L = [f"=== MODE: {r['mode'].upper()} ({r['users']} users, {r['elapsed_real_s']} s real) ==="]
    if r["mode"] == "naive":
        L += [f"sold                     : {r['sold']}  (oversold by {r['oversold_by']})",
              f"final stock counter      : {r['final_stock_counter']}",
              f"available + sold         : {r['available_plus_sold']} (must be {N_UNITS})",
              f"invariants               : {r['invariants']}"]
        return "\n".join(L)
    L.append(f"requests total           : {r['requests_total']} ({r['duplicate_requests']} duplicates)")
    L.append("answered per tier:")
    for k, v in r["answered_per_tier"].items(): L.append(f"  {k:<22}: {v}")
    L += [f"duplicates by tier       : {r['duplicates_by_tier']}",
          f"duplicates collapsed     : {r['duplicates_collapsed']} / {r['duplicate_requests']} (none reached DB twice)",
          f"final rows               : {r['final']}",
          f"final sold               : {r['sold']}",
          f"failed payments          : {r['failed_payments']} (unit released + token returned)",
          f"abandoned (TTL expired)  : {r['abandoned_ttl_expired']}",
          f"resold units             : {r['resold_units']}",
          f"outboxed during outage   : {r['outboxed_events']} (consumer retries while down: {r['outbox_retries_while_down']})",
          f"orders created           : {r['orders_created']} (after outage: {r['orders_created_after_outage']})",
          f"captured payments        : {r['captured_payments']} (max charges/customer: {r['max_charges_per_customer']})",
          f"SKIP LOCKED skips        : {r['skip_locked_hits']}   UNIQUE(customer) rejects: {r['db_unique_rejects']}",
          f"invariant checks run     : {r['invariant_checks']}  violations: {len(r['violations'])}",
          f"invariants               : {r['invariants']}"]
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--naive", action="store_true")
    ap.add_argument("--users", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--json", help="merge result into this JSON file under key 'safe'/'naive'")
    ap.add_argument("--resilience", action="store_true",
                    help="also run the failure-mode scenarios in resilience_sim.py (retry storm, inbox, fencing, hot key)")
    a = ap.parse_args()
    threading.stack_size(256 * 1024)
    r = run_naive(a.users, a.seed) if a.naive else run_safe(a.users, a.seed)
    print(report(r))
    if a.json:
        data = json.load(open(a.json)) if os.path.exists(a.json) else {}
        data[r["mode"]] = r
        json.dump(data, open(a.json, "w"), indent=2)
    if a.resilience:
        import subprocess, sys
        cmd = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "resilience_sim.py"),
               "--seed", str(a.seed)] + (["--json", a.json] if a.json else [])
        subprocess.run(cmd, check=True)
