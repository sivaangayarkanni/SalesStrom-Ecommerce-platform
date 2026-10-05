"""SALESTORM flash-sale load test (Locust) - OPEN-LOOP.

Why open-loop: a normal Locust user waits for each response before sending the next request
(closed loop). When the server stalls, the test quietly sends less traffic and records only one
slow sample per user - "coordinated omission" - so p99 looks great exactly when it is worst.
Here arrivals follow a schedule that does NOT depend on response times, and every latency is
measured from the request's *intended* start time.

Run (10k req/s for 60 s, Poisson arrivals, 200 scheduler users each firing 50 req/s):
  TARGET_RPS=10000 DURATION_S=60 locust -f locustfile.py --host https://api.salestorm.example/v1 \
      --headless -u 200 -r 200 --run-time 70s
Spike to the 500k peak: run from many workers (locust --master / --worker) with TARGET_RPS split.
Expected: ~100 x 201, the rest 409 SOLD_OUT / 503 shed; replays return the same reservation.
Optional: `pip install hdrhistogram` and an HdrHistogram of intended-start latency is printed at the end.
"""
import os, random, time, uuid
import gevent
from locust import User, task, events, constant

SALE_ID, PRODUCT_ID = "42", "X"
TARGET_RPS = float(os.getenv("TARGET_RPS", "10000"))
DURATION_S = float(os.getenv("DURATION_S", "60"))
DUP_RATE, BUY_SHARE = 0.02, 0.25           # 2% duplicate Buy requests; 1 in 4 arrivals is a Buy click

try:                                         # HdrHistogram: 1 us .. 60 s, 3 significant digits
    from hdrh.histogram import HdrHistogram
    HIST = HdrHistogram(1, 60_000_000, 3)
except ImportError:
    HIST = None

from locust.contrib.fasthttp import FastHttpUser


class OpenLoopArrivals(FastHttpUser):
    """Each Locust user is an arrival *scheduler*, not a buyer. It fires requests on its own
    clock in separate greenlets, so a slow response never delays the next arrival."""
    wait_time = constant(0)
    concurrency = 1000                       # connections per scheduler (fasthttp pool)

    def on_start(self):
        n_users = max(1, self.environment.runner.target_user_count or 1)
        self.rate = TARGET_RPS / n_users     # this scheduler's share of the arrival rate
        self.t0 = time.monotonic()

    @task
    def schedule(self):
        next_t = self.t0
        rng = random.Random()
        while time.monotonic() - self.t0 < DURATION_S:
            next_t += rng.expovariate(self.rate)          # Poisson arrivals at a constant mean rate
            delay = next_t - time.monotonic()
            if delay > 0:
                gevent.sleep(delay)
            gevent.spawn(self.one_arrival, next_t, rng.random())
        self.stop()

    def one_arrival(self, intended, r):
        if r < BUY_SHARE:
            key = str(uuid.uuid4())
            self.post_reserve(intended, key, "POST reservation")
            if random.random() < DUP_RATE:                 # same Idempotency-Key resent
                self.post_reserve(time.monotonic(), key, "POST reservation (duplicate)")
        else:
            self.get(intended, f"/sales/{SALE_ID}/stock-status", "GET stock-status (L1)")

    def get(self, intended, path, name):
        with self.client.get(path, name=name, catch_response=True) as resp:
            self.record(intended, name, resp)

    def post_reserve(self, intended, key, name):
        h = {"Authorization": f"Bearer test-{uuid.uuid4()}", "Idempotency-Key": key}
        with self.client.post(f"/sales/{SALE_ID}/reservations", json={"productId": PRODUCT_ID},
                              headers=h, name=name, catch_response=True) as resp:
            self.record(intended, name, resp)

    def record(self, intended, name, resp):
        ok = resp.status_code in (200, 201, 409, 429, 503)  # 503 = load shedder said "come back later"
        resp.success() if ok else resp.failure(f"unexpected {resp.status_code}")
        lat_ms = (time.monotonic() - intended) * 1000       # from INTENDED start, not actual send
        events.request.fire(request_type="INTENDED", name=name + " [intended-start]",
                            response_time=lat_ms, response_length=0,
                            exception=None if ok else Exception(str(resp.status_code)), context={})
        if HIST is not None:
            HIST.record_value(max(1, int(lat_ms * 1000)))


@events.test_stop.add_listener
def dump_histogram(environment, **_):
    if HIST is None:
        return
    for q in (50, 90, 99, 99.9, 99.99):
        print(f"intended-start latency p{q}: {HIST.get_value_at_percentile(q) / 1000:.1f} ms")
    print(f"max: {HIST.get_max_value() / 1000:.1f} ms  samples: {HIST.get_total_count()}")
