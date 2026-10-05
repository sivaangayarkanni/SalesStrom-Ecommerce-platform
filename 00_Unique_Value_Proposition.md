# Unique value proposition — Cache-Hit Ladder

> **Caches can say NO. Only the database can say YES.**

SALESTORM's differentiator is a five-tier **Cache-Hit Ladder** that turns a 10,000-click flash sale into ~100 database writes, while Postgres alone decides who gets a unit.

| Tier | Layer | What it can do | What it cannot do |
|------|--------|----------------|-------------------|
| L0 | Browser | Debounce Buy, cache assets | Sell a unit |
| L1 | CDN + WAF | Serve pages + global `SOLD_OUT` | Sell a unit |
| L2 | In-process | Hot product / sold-out flag | Sell a unit |
| L3 | Redis | Admit ≤100 buyers (token pool), idempotency | Sell a unit |
| L4 | Postgres | Claim a unit row (`SKIP LOCKED`), commit the sale | — |

## Why this wins the jury walkthrough

1. **Speed:** 9,921 of 10,200 clicks answered at the CDN (~10 ms).  
2. **Correctness:** only L4 can say YES → simulation sold exactly **100**, oversold **0**.  
3. **Safety:** Idempotency-Key + `UNIQUE(sale_id, customer_id)` → max **1 charge** per customer.  
4. **Resilience:** outbox + Kafka survive a **30 s** Order Service outage with **0** lost orders.

## The ladder also protects us when things break

The same tiers are where our failure-mode controls sit (full list in [`02_HLD/Production_Failure_Modes.md`](02_HLD/Production_Failure_Modes.md)):

- **L2 + singleflight:** when the hot stock-status key expires, 2,000 concurrent misses become **1** database read, not 2,000.
- **L3 + hot-key salting:** the sale SKU *is* the hot key, so its 100 tokens live in 16 sub-pools; no Redis key took more than 57 of the 10,000 buyers' calls in our run.
- **Before L3, load shedding:** a request that would wait past its deadline gets a fast 503 instead of queueing. After a 2 s blip the system recovered in the first second; naive retries never recovered.
- **L4 stays the only YES:** fencing tokens and an inbox table mean even a paused leader or a redelivered event can't produce a wrong YES.

## Proof

See [`11_AI_Assisted_Validation/simulation/results.json`](11_AI_Assisted_Validation/simulation/results.json) and the Draw.io diagrams in [`DIAGRAMS.md`](DIAGRAMS.md).
