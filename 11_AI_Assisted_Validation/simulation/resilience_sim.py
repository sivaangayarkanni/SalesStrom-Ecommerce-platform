#!/usr/bin/env python3
"""SALESTORM resilience scenarios (stdlib only, seeded, repeatable).

simulate.py checks the sale itself (100 units, payments, outage). This file checks the
failure-mode controls added in 02_HLD/Production_Failure_Modes.md:

  A. retry storm / metastable failure : naive retries vs retry budget + full-jitter backoff + load shedding
  B. 30 s Order Service outage        : at-least-once redelivery, with and without the inbox table
  C. fencing token                    : paused sweeper wakes up with a stale lease
  D. hot key                          : 100 tokens split into 16 salted sub-pools (threads, real locks)
  E. singleflight                     : 2,000 concurrent cache misses on the stock-status key
  F. coordinated omission             : closed-loop vs open-loop latency recording of a 2 s stall

Run:  python3 resilience_sim.py [--seed 42] [--json results.json]
"""
import argparse, json, math, os, random, threading, time
from collections import deque, Counter

# ------------------------------------------------------------------ A. retry storm
def retry_storm(policy, seed, secs=60, tick_ms=10):
    """Checkout tier: capacity 10,000 req/s, fresh load 8,000 req/s (80%).
    Redis failover blip t=10..12 s drops capacity to 1,000 req/s. Client timeout 300 ms."""
    rng = random.Random(seed)
    ticks = secs * 1000 // tick_ms
    cap_ps, fresh_ps, timeout = 10_000, 8_000, 300 // tick_ms
    blip = (10_000 // tick_ms, 12_000 // tick_ms)
    q = deque()                      # [enqueue_tick, deadline_tick, count, attempt]
    qlen = 0
    retry_at = Counter()             # tick -> list of (attempt,count) via dict of counters
    retry_attempt = {}
    fresh_tot = ok_tot = attempts = retries = shed = wasted = gave_up = 0
    budget_tokens = 0.0              # retry budget: retries <= 10% of calls (token bucket)
    per_sec_ok, per_sec_fresh = Counter(), Counter()
    peak_q = 0
    def schedule_retry(t, attempt, n):
        nonlocal gave_up, budget_tokens
        if policy == "naive":
            if attempt >= 5: gave_up += n; return
            d = 100 // tick_ms                         # fixed 100 ms, no jitter
            retry_attempt.setdefault(t + d, Counter())[attempt + 1] += n
        else:
            if attempt >= 3: gave_up += n; return
            allowed = min(n, int(budget_tokens))
            budget_tokens -= allowed
            gave_up += n - allowed                    # budget exhausted -> fail fast, no retry
            for _ in range(allowed):                  # full jitter: U(0, min(cap, base*2^a))
                d = rng.uniform(0, min(2000, 100 * 2 ** attempt)) // tick_ms + 1
                retry_attempt.setdefault(t + int(d), Counter())[attempt + 1] += 1
    for t in range(ticks):
        cap = (1_000 if blip[0] <= t < blip[1] else cap_ps) * tick_ms // 1000
        arrivals = [(1, fresh_ps * tick_ms // 1000)]
        fresh_tot += arrivals[0][1]; per_sec_fresh[t * tick_ms // 1000] += arrivals[0][1]
        if policy != "naive": budget_tokens = min(budget_tokens + 0.1 * arrivals[0][1], 2_000)
        for a, n in sorted(retry_attempt.pop(t, {}).items()):
            arrivals.append((a, n)); retries += n
        for a, n in arrivals:
            attempts += n
            if policy != "naive":                     # load shedder: reject if queue wait > timeout
                room = max(0, cap * timeout - qlen)
                take = min(n, room)
                if n - take:
                    shed += n - take; schedule_retry(t, a, n - take)
                n = take
            if n: q.append([t, t + timeout, n, a]); qlen += n
        peak_q = max(peak_q, qlen)
        budget = cap
        while budget and q:                           # FIFO service
            item = q[0]; take = min(budget, item[2])
            if t <= item[1]:
                ok_tot += take; per_sec_ok[t * tick_ms // 1000] += take
            else:
                wasted += take                        # served after client gave up: wasted work
            item[2] -= take; qlen -= take; budget -= take
            if item[2] == 0: q.popleft()
        while q and q[0][1] < t and policy != "naive":  # controlled: drop expired work, don't serve it
            item = q.popleft(); qlen -= item[2]; schedule_retry(t, item[3], item[2])
        if policy == "naive":                          # client side timeout fires -> retry
            for item in q:
                if item[1] == t - 1 and item[2]:
                    schedule_retry(t, item[3], item[2]); item[1] = -10**9 + item[1]  # mark stale
    # recovery: first full second after the blip where successes >= 95% of fresh arrivals
    rec = None
    for s in range(12, secs):
        if per_sec_ok[s] >= 0.95 * per_sec_fresh[s]:
            rec = s - 12; break
    return {"policy": policy, "fresh_requests": fresh_tot, "attempts": attempts,
            "retry_amplification": round(attempts / fresh_tot, 2), "retries": retries,
            "succeeded": ok_tot, "goodput_pct": round(100 * ok_tot / fresh_tot, 1),
            "wasted_work": wasted, "shed_fast_503": shed, "gave_up": gave_up, "peak_queue": peak_q,
            "recovered_seconds_after_blip": rec if rec is not None else f"not within {secs - 12} s",
            "success_rate_last_10s_pct": round(100 * sum(per_sec_ok[s] for s in range(secs - 10, secs)) /
                                               sum(per_sec_fresh[s] for s in range(secs - 10, secs)), 1)}

# ------------------------------------------------------------------ B. outage + inbox
def outage_inbox(seed, use_inbox, n_events=100):
    rng = random.Random(seed)
    # PaymentAuthorized events from the sale; most land during the 0..30 s outage
    events = sorted((rng.uniform(0, 45), f"evt-{i}") for i in range(n_events))
    deliveries = []                                   # (time, message_id)
    for t, mid in events:
        deliveries.append((t, mid))
        if rng.random() < 0.02: deliveries.append((t + 0.2, mid))   # relay re-publish (lost ack)
    deliveries.sort()
    inbox, orders = set(), Counter()
    attempts_naive = attempts_jitter = 0
    crash_at = 35.0; crashed = False; redeliver = []
    processed_batch = []
    for t, mid in deliveries:
        # consumer retry cost while Order Service is down (0..30 s)
        if t < 30:
            wait = 30 - t
            attempts_naive += int(wait / 0.1)           # retry every 100 ms
            a, clock = 0, 0.0
            while clock < wait:                         # exp backoff, full jitter, cap 5 s
                clock += rng.uniform(0, min(5.0, 0.1 * 2 ** a)); a += 1
            attempts_jitter += a
            t = 30.0
        if use_inbox:
            if mid in inbox: continue                   # INSERT ... ON CONFLICT DO NOTHING -> 0 rows
            inbox.add(mid)
        orders[mid] += 1
        processed_batch.append(mid)
        if not crashed and t >= crash_at:               # crash after DB commit, before offset commit
            crashed = True; redeliver = processed_batch[-10:]
    for mid in redeliver:                               # Kafka redelivers the uncommitted batch
        if use_inbox and mid in inbox: continue
        orders[mid] += 1
    deliv_total = len(deliveries) + len(redeliver)
    return {"inbox": use_inbox, "events": n_events, "deliveries_incl_redelivery": deliv_total,
            "orders_created": sum(orders.values()), "distinct_orders": len(orders),
            "duplicate_orders": sum(v - 1 for v in orders.values()),
            "consumer_attempts_during_outage_fixed_100ms": attempts_naive,
            "consumer_attempts_during_outage_backoff_jitter": attempts_jitter}

# ------------------------------------------------------------------ C. fencing token
def fencing(seed, use_fence):
    """Lease TTL 10 s. Sweeper A (token 7) picks 5 expired reservations, then stalls 15 s (GC/VM pause).
    Lease expires, sweeper B gets token 8, releases those 5 units; 3 are re-reserved by new buyers.
    A wakes and tries its stale writes."""
    rng = random.Random(seed)
    units = {u: {"owner": f"old-{u}", "status": "RESERVED", "last_fence": 0} for u in range(5)}
    lease = {"holder": None, "token": 6, "expires": 0.0}
    def acquire(who, now):
        if lease["holder"] is None or now >= lease["expires"]:
            lease.update(holder=who, token=lease["token"] + 1, expires=now + 10); return lease["token"]
    def write_release(u, token):
        row = units[u]
        if use_fence and token < row["last_fence"]: return False   # UPDATE ... WHERE last_fence_token <= :token
        row.update(owner=None, status="AVAILABLE", last_fence=max(row["last_fence"], token)); return True
    tA = acquire("A", 0.0)
    batch = list(units)                                 # A read its batch at t=0, then pauses
    tB = acquire("B", 11.0)                             # A's lease expired at t=10
    for u in batch: write_release(u, tB)
    resold = rng.sample(batch, 3)
    for u in resold: units[u].update(owner=f"new-{u}", status="RESERVED", last_fence=tB)
    rejected = applied = 0
    for u in batch:                                     # A wakes at t=15, still thinks it is leader
        if write_release(u, tA): applied += 1
        else: rejected += 1
    stolen = sum(1 for u in resold if units[u]["owner"] is None)
    return {"fencing": use_fence, "stale_token": tA, "current_token": tB, "stale_writes_rejected": rejected,
            "stale_writes_applied": applied, "new_buyers_who_lost_their_unit": stolen}

# ------------------------------------------------------------------ D. hot key salted pools
def salted_pool(seed, shards=16, buyers=10_000, tokens=100, nodes=50):
    pools = [tokens // shards + (1 if i < tokens % shards else 0) for i in range(shards)]
    locks = [threading.Lock() for _ in range(shards)]
    ops = Counter()
    hint = [[False] * shards for _ in range(nodes)]   # per-node L2 hint: "this sub-pool is empty"
    granted, gl = [], threading.Lock()
    go = threading.Event()
    def buyer(b):
        r = random.Random(seed * 7919 + b); start = r.randrange(shards)
        empty_seen = hint[b % nodes]                  # buyer lands on app node b % nodes
        go.wait()
        for k in range(shards):                       # fallback probing: next shard on empty
            s = (start + k) % shards
            if empty_seen[s]: continue
            with locks[s]:
                ops[s] += 1
                if pools[s] > 0:
                    pools[s] -= 1
                    with gl: granted.append(b)
                    return
                empty_seen[s] = True
        with gl: local_no[0] += 1                     # every sub-pool known empty on this node
    local_no = [0]
    th = [threading.Thread(target=buyer, args=(b,)) for b in range(buyers)]
    for t in th: t.start()
    go.set()
    for t in th: t.join()
    return {"sub_pools": shards, "tokens": tokens, "buyers": buyers, "tokens_granted": len(granted),
            "distinct_buyers_granted": len(set(granted)), "tokens_left": sum(pools),
            "app_nodes": nodes, "sold_out_answers": local_no[0], "redis_ops_total": sum(ops.values()), "max_ops_on_one_key": max(ops.values()),
            "ops_on_single_unsalted_key_would_be": buyers}

# ------------------------------------------------------------------ E. singleflight
def singleflight(n=2_000):
    def run(sf):
        db_reads = [0]; lock = threading.Lock(); inflight = {}; cache = {}; go = threading.Event()
        def load():
            with lock: db_reads[0] += 1
            time.sleep(0.02); return "IN_STOCK:37"
        def get(key):
            go.wait()
            if not sf: return load()                     # cache-aside without coalescing
            with lock:
                if key in cache: return cache[key]        # L2 hit after the shared load finished
                f = inflight.get(key)
                leader = f is None
                if leader: f = inflight[key] = {"ev": threading.Event(), "val": None}
            if leader:
                f["val"] = load()
                with lock: cache[key] = f["val"]; inflight.pop(key, None)
                f["ev"].set()
            else: f["ev"].wait()
            return f["val"]
        th = [threading.Thread(target=get, args=("stock:sku42",)) for _ in range(n)]
        for t in th: t.start()
        go.set()
        for t in th: t.join()
        return db_reads[0]
    return {"concurrent_misses": n, "db_reads_without_singleflight": run(False),
            "db_reads_with_singleflight": run(True)}

# ------------------------------------------------------------------ F. coordinated omission
def coordinated_omission(rate=1_000, secs=10, svc_ms=1.0, stall=(5.0, 7.0)):
    def p(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))]
    def latency_at(start):                            # server frozen during stall
        if stall[0] <= start < stall[1]: return (stall[1] - start) * 1000 + svc_ms
        return svc_ms
    closed, t = [], 0.0                               # closed loop: next request after previous returns
    gap = 1.0 / rate
    while t < secs:
        l = latency_at(t); closed.append(l); t += max(gap, l / 1000)
    opened = [latency_at(i * gap) for i in range(int(secs * rate))]   # open loop, measured from intended start
    return {"closed_loop_samples": len(closed), "closed_loop_p99_ms": round(p(closed, .99), 1),
            "closed_loop_max_ms": round(max(closed), 1), "open_loop_samples": len(opened),
            "open_loop_p99_ms": round(p(opened, .99), 1), "open_loop_p90_ms": round(p(opened, .90), 1),
            "open_loop_max_ms": round(max(opened), 1)}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=42); ap.add_argument("--json")
    a = ap.parse_args(); threading.stack_size(256 * 1024)
    r = {"retry_storm": {"naive": retry_storm("naive", a.seed), "controlled": retry_storm("controlled", a.seed)},
         "order_outage": {"no_inbox": outage_inbox(a.seed, False), "with_inbox": outage_inbox(a.seed, True)},
         "fencing": {"redis_lock_only": fencing(a.seed, False), "with_fencing_token": fencing(a.seed, True)},
         "hot_key": salted_pool(a.seed), "singleflight": singleflight(), "coordinated_omission": coordinated_omission()}
    ok = (r["order_outage"]["with_inbox"]["duplicate_orders"] == 0
          and r["fencing"]["with_fencing_token"]["new_buyers_who_lost_their_unit"] == 0
          and r["hot_key"]["tokens_granted"] == 100 and r["hot_key"]["distinct_buyers_granted"] == 100
          and r["singleflight"]["db_reads_with_singleflight"] == 1)
    r["checks"] = "PASS" if ok else "FAIL"
    for k, v in r.items():
        print(f"== {k}"); print(json.dumps(v, indent=2) if isinstance(v, dict) else v)
    if a.json:
        data = json.load(open(a.json)) if os.path.exists(a.json) else {}
        data["resilience"] = r; json.dump(data, open(a.json, "w"), indent=2)

if __name__ == "__main__":
    main()
