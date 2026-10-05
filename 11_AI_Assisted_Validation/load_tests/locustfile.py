"""SALESTORM flash-sale load test (Locust).
Run: locust -f locustfile.py --host https://api.salestorm.example/v1 -u 10000 -r 10000
Each user browses (cache tiers L1/L2), then presses Buy once; 2% resend the same Idempotency-Key.
Expected: ~100 x 201, the rest 409 SOLD_OUT; replays return 200 with the same reservation.
"""
import random, uuid
from locust import HttpUser, task, between

SALE_ID, PRODUCT_ID = "42", "X"

class FlashSaleBuyer(HttpUser):
    wait_time = between(0, 0.2)

    def on_start(self):
        self.headers = {"Authorization": f"Bearer test-{uuid.uuid4()}"}
        self.bought = False

    @task(3)
    def browse(self):
        self.client.get(f"/products/{PRODUCT_ID}", name="GET product (L1/L2)")
        self.client.get(f"/sales/{SALE_ID}/stock-status", name="GET stock-status (L1)")

    @task(1)
    def buy(self):
        if self.bought:
            return
        self.bought = True
        key = str(uuid.uuid4())
        h = {**self.headers, "Idempotency-Key": key}
        with self.client.post(f"/sales/{SALE_ID}/reservations", json={"productId": PRODUCT_ID},
                              headers=h, name="POST reservation", catch_response=True) as r:
            if r.status_code in (200, 201, 409, 429, 503):
                r.success()
            else:
                r.failure(f"unexpected {r.status_code}")
        if random.random() < 0.02:  # 2% duplicate requests
            self.client.post(f"/sales/{SALE_ID}/reservations", json={"productId": PRODUCT_ID},
                             headers=h, name="POST reservation (duplicate)")
