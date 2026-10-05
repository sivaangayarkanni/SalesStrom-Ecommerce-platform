# 08 – Scalability & Reliability Design

## 1. Horizontal scaling
- All services stateless (state in Redis/Postgres/Kafka) ⇒ add pods behind the load balancer.
- **Pre-scale before sale start** (scheduled scaling) + HPA on request rate; autoscalers are too slow for a 1-second spike.
- Caches pre-warmed (product page pushed to CDN, sale config loaded into L2, 100 tokens loaded into Redis).

## 2. What changes at 50× traffic (10k → 500k req/s)
| Layer | At 50× | Why it still works |
|---|---|---|
| L0/L1 | More CDN POP capacity, stricter WAF bot rules, `SOLD_OUT` pushed at edge | Most extra traffic is "already sold out" – answered at the edge |
| Waiting room | Admits a fixed rate (e.g. 5k/s) regardless of incoming | Origin load is capped, not proportional |
| Gateway / services | More pods (pre-scaled), per-user rate limits | Stateless |
| L3 Redis | Token pool sharded (e.g. 10 keys × 10 tokens, user hashed to shard, fall through to next shard); more read replicas for idempotency lookups | Removes single hot key |
| L4 Postgres | **Same ~105 writes for 100 units** – DB load depends on stock, not traffic. For many products: partition `orders` by month, shard by customer_id, read replicas for catalog, PgBouncer connection pooling | Writes bounded by inventory |
| Kafka | More partitions + consumers | Async, absorbs bursts |

**Key insight: thanks to the token pool, DB write load scales with stock (100), not with traffic (10,000 or 500,000).**

## 3. Bottlenecks and mitigations
| Bottleneck | Mitigation |
|---|---|
| Hot inventory row | 100 unit rows + SKIP LOCKED |
| Redis single key | Sharded pools; local SOLD_OUT flag stops calls once empty |
| DB connections | PgBouncer; only token holders reach DB |
| Payment gateway | Circuit breaker, secondary provider, async capture |
| Cache stampede at sale start | Pre-warm, single-flight, jittered TTL |
| Kafka lag | Partition by aggregate id, autoscale consumers, lag alert |

## 4. Failure handling
| Failure | Detection | Recovery | What user sees |
|---|---|---|---|
| **Postgres primary down** | Health checks | Automatic failover to **synchronous standby** (RPO≈0, RTO < 1 min target); writes paused, waiting room holds users; Redis tokens are re-synced from DB (`tokens = available units`) after failover | "High demand, please wait" – no lost orders |
| **Redis down** | Errors/timeouts | Degrade: gateway admits a small fixed rate to DB conditional path; idempotency falls back to DB table; tokens rebuilt from DB when back | Slower, still correct |
| **Payment gateway down/slow** | Breaker opens | Fail fast; route to secondary provider; reservations held; TIMEOUT payments reconciled | "Payment temporarily unavailable, your item is held" |
| **Order Service down** | Consumer lag | Events wait in Kafka; idempotent replay; void after SLA | "Order processing" |
| **Kafka down** | Relay errors | Outbox table keeps events; relay resumes | Slight delay |
| **Pod crash mid-transaction** | — | DB transaction rolls back; token returned by reconciliation (tokens vs DB counts) | Retry with same key |
| **CDN down** | Synthetic checks | DNS fail-over to backup CDN; rate limiter + waiting room protect origin | Slower pages |

**Self-healing invariant job (every 10 s):** compare Redis token count with `inventory.available`; check `available+reserved+sold = total`; fix tokens, alert on DB mismatch (should be impossible due to CHECK).

## 4a. Overload and partial failure (see `02_HLD/Production_Failure_Modes.md`)
| Situation | What we do | Evidence |
|---|---|---|
| 2 s Redis failover at 80% load | `LoadShedder` + retry budget + full-jitter backoff | model: recovered in the first second, 97.2% goodput; naive retries never recovered (16.7% goodput) |
| Hot SKU on one Redis key | 16 salted sub-pools + per-node empty hints | model: max 57 ops on one key instead of 10,000; exactly 100 tokens granted |
| Stock-status key expires mid-sale | Singleflight + TTL jitter | model: 2,000 misses → 1 DB read |
| One pod / PSP endpoint slow but "healthy" | Outlier ejection, P2C balancing, phi-accrual | design |
| Sweeper or relay pauses past its lease | Fencing token checked by Postgres | model + Postgres 17 check |
| Sale overload | Separate cell; regular store unaffected | design |

**Capacity (Little's law, L = λW):** reserve path 10,000 req/s × 20 ms = 200 in flight → 18 pods × 16 workers (69% busy). DB: ~107 requests ever reach Postgres; at 100 TX/s × 30 ms only ~3 connections are busy, so a PgBouncer pool of 40 is plenty. Target utilization < 70% everywhere.

## 5. Async reliability
- Timeouts on every remote call; retries only for idempotent operations, exponential backoff with full jitter, retry budget 10%.
- Dead-letter topics for poison messages, with alert and replay tool.
- Idempotent consumers: `inbox_message (consumer, message_id)` table in the same TX + unique constraints.
- Reconciliation worker: stuck TIMEOUT payments, authorized-without-order, expired reservations, nightly gateway settlement compare.

> **Defend it**
> - "At 50× traffic our database does the same ~105 writes – write load scales with stock, not with users."
> - "If Redis dies we get slower, not wrong; if the DB fails over, the sync standby means no order is lost."
