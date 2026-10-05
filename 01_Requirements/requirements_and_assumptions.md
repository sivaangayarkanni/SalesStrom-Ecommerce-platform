# 01 – Requirements & Assumptions (SALESTORM)

> **Unique factor – the Cache-Hit Ladder:** every request is answered at the *cheapest tier that can answer it correctly*.
> **Rule:** *Caches can say NO. Only the database can say YES.*

## 1. Business problem
Flash sale: **Product X, 100 units, 10,000 customers press "Buy Now" at the same instant.**
Sell exactly ≤100, never double-charge, and every paid customer ends with a valid order – even when services fail.

## 2. Functional requirements (per pipeline step)
| # | Step | Requirement |
|---|------|-------------|
| F1 | Product Discovery | Browse/search products and view live sale details and stock status (in stock / sold out). |
| F2 | Cart | Add/remove items; cart persists across sessions. |
| F3 | Inventory Check | Instantly tell the user whether stock is still available. |
| F4 | Reservation | Hold one unit per customer for **5 minutes**; auto-release when expired. |
| F5 | Checkout | Validate reservation, apply price/coupon (pricing strategy), start payment. |
| F6 | Payment | Authorize, capture, fail, time out, refund/void; duplicate requests collapse to one transaction. |
| F7 | Order | Create order after payment; follow defined lifecycle; support cancel. |
| F8 | Fulfilment/Shipment | Create shipment through a delivery partner; track status. |
| F9 | Notification | Notify on reservation, payment, order, shipment, delivery events. |
| F10 | Delivery Tracking | Customer can query current shipment state. |
| F11 | Sale rules | One unit per customer per sale; sale start/end times enforced. |

## 3. Hard guarantees vs targets (the key slide)
| HARD GUARANTEES – never violated | Protected by | TARGETS – best effort | Sacrificed when missed |
|---|---|---|---|
| G1 Sold units ≤ 100; stock never negative | DB row lock on unit rows (`SKIP LOCKED`) + `CHECK (available >= 0)` + `CHECK (available + reserved + sold = total)` | T1 Buy response p99 < 200 ms | Customer waits longer / waiting room |
| G2 One reservation per customer per sale | `UNIQUE (sale_id, customer_id)` | T2 Checkout availability 99.95% during sale | Some users get "try again" (503 + Retry-After) |
| G3 No customer charged twice | Idempotency key (unique) + unique `provider_txn_ref`; retries reuse the same key | T3 Order created ≤ 60 s after payment | Order shows "processing" a bit longer |
| G4 Every captured payment ends in exactly one valid order **or** a refund/void | Authorize-then-capture + transactional outbox + reconciliation | T4 Expired reservations released ≤ 5 s after expiry | Unit returns to sale slightly late |
| G5 Every state change is auditable | Append-only `audit_log` + outbox events | T5 Cache hit ratio ≥ 95% at L1+L2 for reads (estimate) | More load reaches origin |

**One-liner:** *Under failure we give up speed and availability – never correctness.*

### 3a. Resilience guarantees vs targets (added after our failure-mode review, see `02_HLD/Production_Failure_Modes.md`)
| HARD GUARANTEES – never violated | Protected by | TARGETS – best effort | Sacrificed when missed |
|---|---|---|---|
| G6 A redelivered event never creates a second order, SMS or shipment | `inbox_message` PK `(consumer, message_id)` in the same TX as the business write | T6 Recover to ≥ 95% success within 5 s after a 2 s dependency blip | Some buyers get a fast 503 + `Retry-After` |
| G7 A paused/old leader (sweeper, relay) can never overwrite newer state | `lease.fence_token` (monotonic) checked in every `UPDATE … WHERE last_fence_token <= :token` | T7 Retries ≤ 10% of calls (retry budget); total load amplification ≤ 1.1× | Clients fail fast instead of retrying |
| G8 One live reservation per unit, whatever the isolation level | Partial UNIQUE `uq_reservation_one_live_per_unit` + `SKIP LOCKED` + CHECKs | T8 Steady-state utilization < 70% on every tier (Little's law sizing) | Waiting room admits fewer per second |
| G9 A late payment for an expired reservation is voided or refunded, never silently kept | event time + watermark → `reconciliation_case` | T9 p99 measured open-loop (intended start, HdrHistogram) within the T1 target | Report it honestly; fix capacity |
| | | T10 Flash-sale overload doesn't move regular checkout p99 (separate cell) | Sale cell sheds load first |

## 4. Non-functional requirements (measurable)
| Quality | Requirement |
|---|---|
| Throughput | 10,000 req/s normal; design reasoned up to **500,000 req/s** at peak |
| Latency | Browse p99 < 50 ms (CDN hit); Buy decision p99 < 200 ms; payment authorize p99 < 2 s (gateway-bound) |
| Availability | 99.95% for checkout path during sale; graceful degradation (waiting room) instead of collapse |
| Consistency | **Strong** for inventory, payment, order (ACID in Postgres); **eventual** for catalog cache, notifications, tracking |
| Security | OAuth2/JWT, TLS everywhere, rate limiting, input validation, no card data stored (PCI tokenization) |
| Recovery | RPO ≈ 0 for orders/payments (sync replica); RTO < 1 min DB failover; outbox guarantees no lost events |
| Observability | Per-tier cache hit ratio, reservation success/fail, payment fail rate, queue lag, invariant alarms |
| Overload behaviour | Load shedding at 300 ms expected queue wait; retry budget 10%; full-jitter backoff (base 100 ms, cap 2 s); max 3 attempts, idempotent calls only |
| Isolation | Flash sale in its own cell (pods, Redis, DB pool, limits); outlier ejection + power-of-two-choices load balancing inside the cell |
| Load-test validity | Open-loop arrivals at a constant rate; latency from intended start time (no coordinated omission) |

## 5. Assumptions & constraints
- Users are logged in before the sale (session warm-up); 1 unit per customer.
- Reservation TTL = 5 min; payment through an external gateway (Razorpay/Stripe class) supporting authorize/capture/void and idempotency keys.
- Single region, 3 availability zones; Postgres is the system of record.
- Sale config and the product page are published (and caches pre-warmed) **before** sale start.
- All numbers below are **planning estimates**, not measured benchmarks.

## 6. Traffic estimate – back-of-envelope (estimates)
**Critical scenario:** 10,000 Buy clicks, 100 units.
- 9,900 requests (99%) *must* fail → make failure as cheap as possible.
- Redis token pool hands out 100 tokens → **~100 requests reach the DB**, plus ~5 resale attempts from the ~5% failed payments → **~105 DB writes total**.
- After tokens run out, a `SOLD_OUT` flag is pushed to every service (L2) and the CDN (L1) → later clicks never reach origin.

**Peak 500k req/s – where each request is answered (Cache-Hit Ladder, estimates):**
| Tier | Answers | Share of traffic (est.) | Latency (est.) |
|---|---|---|---|
| L0 Browser | Cached page, countdown, debounced Buy button | removes repeat clicks | 0 ms |
| L1 CDN/WAF | Product page, images, `SOLD_OUT` flag, bot blocking, rate limit | ~80–90% | 5–20 ms |
| L2 In-process cache | Hot product/sale config, local sold-out boolean | ~8–15% | < 1 ms |
| L3 Redis | Token pool (yes/no on admission), idempotency replay, cart | ~1–2% | ~1 ms |
| L4 Postgres | Committing the actual reservation/order/payment | ≈ 100s of writes in total | 5–20 ms |

## 7. Critical dependencies
Payment gateway (external, can be slow/fail) · Redis cluster (fast path; failure ⇒ slower DB path, still correct) · Postgres primary (single source of truth; sync standby) · Kafka (async workflow; outbox buffers if down) · CDN (edge; failure ⇒ origin protected by rate limiter + waiting room).

> **Defend it**
> - "We split guarantees from targets so we know exactly what we're allowed to give up under failure."
> - "99% of requests must fail – our job is to make failure cheap, and the Cache-Hit Ladder does that."
> - "Caches can say NO; only the database can say YES – so caching never risks overselling."
