# 12 – Final 5-Minute Pitch Script

**0:00–0:30 Problem** – "100 units, 10,000 people pressing Buy at the same instant. 99% of them *must* be told no. Most systems fail by letting all 10,000 fight inside the database. Our answer: make the 'no' cheap and the 'yes' bulletproof."

**0:30–1:00 Requirements** – Show the guarantees vs targets table. "Five things never break – no oversell, one per customer, no double charge, every captured payment has an order, everything audited. Latency and availability are targets. Under failure, we give up speed, never correctness."

**1:00–2:00 HLD** – Show the architecture + Cache-Hit Ladder. "Every request is answered at the cheapest tier that can answer correctly: browser, CDN, in-process cache, Redis, and only then Postgres. Our rule: caches can say NO, only the database can say YES. Reserve and authorize are synchronous because the user is waiting; order, capture, shipment, notification are asynchronous through an outbox, so a crashed service loses nothing."

**2:00–3:00 Critical design (10,000 vs 100)** – Walk the jury answer below (short version). "Redis hands out exactly 100 admission tokens. Token holders claim one of 100 unit rows with SELECT FOR UPDATE SKIP LOCKED – no single hot row, nobody waits, and on the last unit one wins and the other gets SOLD_OUT instantly. CHECK constraints make overselling impossible even with a bug. Our database sees about 105 writes, not 10,000."

**3:00–3:45 Payment & order** – "We authorize first and capture only after the order exists. Payment fails → unit released and resold. Timeout means *unknown* → we query the gateway with the same idempotency key, never charge twice. Order Service down for 30 s → event waits in Kafka, order created on recovery, captured then; if it never recovers we void, so nobody is charged without an order. And the race nobody talks about – reservation expires one second before payment succeeds – is solved with a fencing version."

**3:45–4:30 LLD + SOLID + patterns (Payment module)** – "PaymentService depends on the PaymentGateway interface (DIP). Razorpay and Stripe are Adapters, built by a Factory, wrapped in a Circuit Breaker decorator. Adding PayU is one new class and one registration line – OCP. Order lifecycle uses the State pattern, so illegal transitions can't even be coded."

**4:30–5:00 Scale, reliability, validation** – "At 50× traffic the database does the same ~105 writes – write load scales with stock, not users. Redis down: slower, still correct. DB fails over to a sync standby: no order lost. And we proved it: our simulation of 10,000 users with 5% payment failures, 2% duplicates and a 30 s Order outage sold exactly 100 with zero invariant violations – while the naive version oversold 550 units."

---

## Final jury question – full walk-through
*"100 units remaining, 10,000 customers click Buy Now simultaneously. What happens?"*

1. **Before the sale:** product page pushed to the CDN, sale config loaded into every pod's cache (L2), 100 tokens loaded into Redis, services pre-scaled.
2. **L0 browser:** double-clicks are debounced; each click carries a unique Idempotency-Key.
3. **L1 CDN/WAF:** bots and over-limit clients blocked. Stock not yet sold out, so the request goes to origin.
4. **Gateway:** verifies JWT, per-user rate limit, checks Idempotency-Key format; waiting room admits a controlled rate.
5. **L2 local cache:** sold-out flag is false → continue.
6. **L3 Redis:** idempotency key not seen → atomic Lua pop from the token pool. The first 100 requests get tokens; the rest get **409 SOLD_OUT in ~1 ms**. The pod that sees the pool empty publishes `StockSoldOut` → every pod's L2 flag flips and the CDN starts serving SOLD_OUT at the edge – from now on requests never reach us.
7. **L4 Postgres (100 token holders):** one transaction each – `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` claims a different unit row, inserts the reservation (UNIQUE per customer, UNIQUE idempotency key), updates counters (CHECK ≥ 0), writes `ReservationCreated` to the outbox → **201 RESERVED, expires in 5 min.**
8. **Duplicates:** same key → stored response replayed; new key same customer → ALREADY_RESERVED.
9. **Checkout + payment (sync):** price via PricingStrategy, authorize at gateway with idempotency key → `PaymentAuthorized` in outbox. ~95 succeed.
10. **~5 fail:** `PaymentFailed` → reservation released → unit row AVAILABLE, token back in Redis, `StockReleased` clears the SOLD_OUT flag → a waiting customer gets that unit. Same for reservations that expire unpaid.
11. **Order (async):** Order Service consumes `PaymentAuthorized`, creates the order (unique per payment) → `OrderCreated` → payment captured → reservation SOLD → order CONFIRMED → notification sent. If Order Service is down, events wait and are processed on recovery.
12. **End state:** exactly 100 units SOLD, 100 orders CONFIRMED, 100 captures, every other customer told SOLD_OUT quickly, `available + reserved + sold = 100` at every moment – checked by an alerting invariant job.
