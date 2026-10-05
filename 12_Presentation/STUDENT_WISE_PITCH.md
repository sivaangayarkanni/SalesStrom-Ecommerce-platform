# SALESTORM: Student-wise Pitch and Explanation

Total pitch: 5 minutes. 3 speakers. Slide numbers refer to `SALESTORM_Final_Presentation.pptx` (33 slides).
With 3 students: Student 1 = Architect, Student 2 = LLD + Concurrency, Student 3 = Data/API + Reliability.

---

## PART A: The 5-minute pitch (memorise this)

### Student 1: Opening + Architecture (0:00 to 1:45) - slides 1 to 11
"Good afternoon. We are team SALESTORM.

The problem: 100 units, 10,000 buyers clicking Buy Now in the same second, up to 500,000 requests per second. The hard part is not speed. It is selling exactly 100, never 101, never charging anyone twice, and surviving a 30-second Order Service outage.

A naive design, where every request reads stock and decrements it, sold 650 units in our simulation. That is 550 angry customers.

Our answer is the Cache-Hit Ladder. One rule: caches can say NO, only the database can say YES.
- L0, the browser, blocks repeat clicks.
- L1, the CDN, serves the page and a SOLD OUT flag.
- L2, in-memory cache on every server, holds the hot product.
- L3, Redis, holds exactly 100 tokens split across 16 pools.
- L4, Postgres, is the only place a sale actually happens.

In our simulation of 10,200 requests, 9,921 were answered at the CDN. Only 107 ever reached the database. Exactly 100 were sold.

The flash sale runs in its own cell, with its own pods, Redis and database pool, so the sale can never take down normal shopping. Now Student 2 will show how one purchase works inside."

### Student 2: Inside one purchase (1:45 to 3:15) - slides 12 to 18, 24
"When a buyer gets a Redis token, the Checkout Orchestrator runs a saga: reserve, pay, confirm.

Reserve: every unit is its own row in Postgres. We run SELECT ... FOR UPDATE SKIP LOCKED. Two buyers never wait on the same row and never get the same unit. A CHECK constraint and a unique index make a 101st sale physically impossible. This also prevents write skew, where two transactions both read 'one left' and both sell it.

Pay: we authorize first and capture only after the order is confirmed. If anything fails, we void the authorization, so nobody is charged for nothing.

The design follows SOLID. Payment providers sit behind a Factory and Adapter, so switching Razorpay to Stripe changes no business code. Facade, Saga, Strategy, Circuit Breaker and Outbox each solve one specific problem. Student 3 will show what happens when things fail."

### Student 3: Data, failure and proof (3:15 to 5:00) - slides 19 to 33
"Every request carries an Idempotency-Key. The 2% duplicate clicks get the same answer back, not a second order.

When payment succeeds, we write the order and an outbox row in the same transaction. A relay publishes to Kafka. Consumers keep an inbox table, so each message is processed once.

The 30-second Order Service outage: messages wait in Kafka, retries use exponential backoff with jitter and a retry budget. Without the inbox we got 13 duplicate orders. With it, zero.

We designed for 14 production failure modes. Retry storm: naive retries hit 4.26 times the load and never recovered. Ours stayed at 1.01 times and recovered in one second. A paused worker with an expired lock: a Redis lock alone lost units for 3 buyers; our fencing token blocked the stale writes. A cache stampede of 2,000 misses became one database read.

Our load tests are open-loop, because closed-loop tests hide stalls: same 2-second stall, closed-loop said p99 was 1 ms, open-loop showed the truth, 1.9 seconds.

Result: exactly 100 sold, zero oversell, zero double charges, 415 invariant checks, zero violations. Everything is live: scan the QR code. Caches can say NO. Only the database can say YES. Thank you."

---

## PART B: Deep explanation per student (for questions)

### Student 1: System Architect
Folders: `01_Requirements`, `00_Unique_Value_Proposition.md`, `02_HLD`, `08_Scalability_Reliability`, ADR-001/003/004/005/010.
- **Requirements:** hard guarantees (exactly 100 sold, no double charge, no lost paid order) never bend. Targets (p99 latency, availability) degrade gracefully under load.
- **Why the ladder works:** 97% of traffic is answered at the CDN. Each tier only forwards what it cannot answer. The DB sees ~100 writes, not 500,000.
- **Scaling:** stateless services scale horizontally on Kubernetes, pre-scaled before the sale. Waiting room admits at a measured rate.
- **Little's law:** in-flight = arrival rate x time. 10,000 req/s x 20 ms = 200 in flight, so the pod/worker count is sized for that, under 70% utilisation, because queues blow up above that.
- **Load balancing:** power of two choices. Pick 2 servers at random, send to the less busy one. Unhealthy-but-alive (gray failure) nodes are ejected based on real success rate and latency.
- **Cell architecture:** the flash sale has its own cell. Sharding is for data size; cells are for blast radius.

Likely questions:
- *Why not just add servers?* More servers don't fix retries feeding on themselves. Admission control and load shedding do.
- *What if Redis dies?* Redis can only say NO. If it is down we shed load; Postgres still guarantees correctness.
- *Why SQL?* We need transactions and row locks for exactly-100. That's ADR-004.

### Student 2: LLD and Design Engineer
Folders: `03_LLD`, `06_SOLID`, `07_Design_Patterns`, `14_Diagram_Screenshots`.
- **Key classes:** CheckoutController, IdempotencyFilter, CheckoutFacade, CheckoutSaga, ReservationService, InventoryUnitRepository, PaymentService, PaymentProviderFactory, CircuitBreakerGateway, OutboxWriter. Resilience: LoadShedder, RetryBudget, BackoffWithJitter, SingleflightCache, HotKeySaltedTokenPool, LeaseManager + FencingToken, InboxDeduplicator, PhiAccrualDetector.
- **SOLID:** S: each class one job (Reservation vs Payment). O: new payment provider = new adapter, no edits. L: any PaymentProvider is swappable. I: small interfaces (Reservable, Payable). D: services depend on interfaces, not Redis/Postgres directly.
- **Patterns:** Facade (one checkout entry), Saga (multi-step with compensation), Strategy (pricing), Factory + Adapter (payment providers), Circuit Breaker (slow gateway), Outbox (reliable events), State (reservation/order lifecycle).
- **States:** Reservation: HELD, CONFIRMED, EXPIRED, RELEASED. Order: CREATED, PAID, CONFIRMED, SHIPPED, CANCELLED/REFUNDED.
- **Concurrency:** SKIP LOCKED means buyers take different free rows instead of queuing on one. Pessimistic locking on unit rows (ADR-008) because contention is extreme.

Likely questions:
- *Two users click Buy on the last unit at the same instant?* Both run SKIP LOCKED. One gets the row; the other sees no free row and gets SOLD OUT. No overselling.
- *Optimistic or pessimistic?* Pessimistic. With 10,000 buyers on 100 rows, optimistic retries would explode.
- *Where is Open/Closed?* Payment adapters.

### Student 3: Data, API and Reliability Engineer
Folders: `04_Database`, `05_API`, `09_Security_Observability`, `11_AI_Assisted_Validation`, `02_HLD/Production_Failure_Modes.md`, ADR-002/006/007/008/009.
- **Database:** 22 tables. inventory_unit (one row per unit), inventory_reservation, orders, payment, idempotency_record, outbox_event, inbox_message, lease, reconciliation_case.
- **API:** POST /reserve, POST /checkout, GET /orders/{id}. Idempotency-Key header. 409 = sold out, 503 + Retry-After = shed load. Live on the Swagger page.
- **Events:** outbox = order and event in one transaction. Inbox = consumer stores message id, ignores repeats. Together: at-least-once delivery + idempotent handling = effectively once.
- **Fencing token:** the expiry sweeper holds a lease with an increasing number. The DB rejects writes with an older number, so a paused old worker can't release a unit that's already resold.
- **Late events:** a payment webhook arriving after the hold expired goes to reconciliation, and the authorization is voided or refunded (event time, not processing time).
- **Security:** JWT, rate limiting, WAF and bot protection at the edge, metrics/logs/traces.
- **Proof:** simulation 10,200 requests, 100 sold, 415 checks, 0 violations. Postgres check script passes on a real database.

Likely questions:
- *Payment succeeds but order creation fails?* The payment and outbox row are committed; the order is created when the Order Service is back. If the hold expired, reconciliation refunds.
- *Duplicate requests?* Same Idempotency-Key returns the stored response.
- *How do you know it works?* Simulation, Postgres constraint tests, and open-loop Locust/JMeter plans.

---

## Handover lines
- Student 1 to 2: "Now Student 2 will show how one purchase works inside."
- Student 2 to 3: "Student 3 will show what happens when things fail."
- Closing (Student 3): "Caches can say NO. Only the database can say YES. Thank you."
