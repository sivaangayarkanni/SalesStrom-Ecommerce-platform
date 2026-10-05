# 12 – Jury Q&A (rehearse these)

**Why is this the correct service boundary?**
Each service owns one kind of truth and its tables: Inventory owns stock, Payment owns money, Order owns the order lifecycle. Stock decisions need strong consistency and must never wait on slow parts (payment gateway, notifications), so Inventory is isolated and is the only writer of stock.

**Where exactly is inventory consistency guaranteed?**
In one Postgres transaction in the Inventory Service: claiming a row in `inventory_unit` with `FOR UPDATE SKIP LOCKED`, inserting the reservation, and updating counters protected by `CHECK (available >= 0)` and `CHECK (available + reserved + sold = total)`. Caches and Redis only filter.

**What happens if two requests reach the inventory service at the same time?**
Both run SKIP LOCKED. They lock different unit rows if available. If one unit is left, one transaction locks it, the other skips it, finds nothing and returns SOLD_OUT immediately – no waiting, no deadlock, deterministic result.

**Why did you select this concurrency strategy?**
A single counter row serializes 10,000 requests (pessimistic) or causes retry storms (optimistic). Unit rows spread contention over 100 rows, nobody waits, and we get per-unit audit. Redis tokens make sure only ~100 requests even try. Conditional UPDATE is our Redis-down fallback.

**Why is this operation synchronous while another is asynchronous?**
Reserve and authorize are synchronous because the user is waiting for "yes/no". Order creation, capture, shipment and notifications are asynchronous so that a slow or crashed downstream service can't fail a purchase that was already paid for.

**How does the design recover from payment success followed by order failure?**
The payment and its `PaymentAuthorized` event are written in one transaction (outbox). The event waits in Kafka until Order Service recovers; the consumer is idempotent (unique per payment). We only authorized, so capture happens after the order exists. If the order isn't created within the SLA, the saga voids the authorization and releases the unit.

**Which component is the likely bottleneck and how will it scale?**
Without our design, the inventory row in the DB. With it, the Redis token-pool key and the edge. We shard the token pool across keys, flip the local SOLD_OUT flag so empty pools stop being called, and push SOLD_OUT to the CDN. DB write load stays ~105 because it scales with stock, not traffic.

## Practical demo traces (1-line answers)
| Trace | Answer |
|---|---|
| One successful purchase | Token → unit claimed → 201 → authorize → outbox → order → capture → SOLD → notify |
| Failed payment | PaymentFailed → reservation RELEASED → unit AVAILABLE + token returned → resold |
| Duplicate Buy | Same key → stored response replayed; new key same user → 409 ALREADY_RESERVED |
| Payment ok, Order down 30 s | Event waits in Kafka, reservation extended, order created on recovery, then capture |
| Inventory reaches zero | Pool empty → StockSoldOut → L2 flags + CDN serve SOLD_OUT; DB untouched |
| 50× traffic | Absorbed at CDN + waiting room; Redis sharded; DB still ~105 writes |
| DB fails | Failover to sync standby, waiting room holds users, tokens re-synced from DB |
| Gateway fails | Circuit breaker opens, secondary provider or "try again", reservations held, timeouts reconciled |
| AI validation | Simulation: 100 sold, 0 violations; naive mode oversold 550 – proves checks are real |
