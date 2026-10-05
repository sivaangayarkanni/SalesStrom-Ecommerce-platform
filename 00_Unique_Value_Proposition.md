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

## Proof

See [`11_AI_Assisted_Validation/simulation/results.json`](11_AI_Assisted_Validation/simulation/results.json) and the Draw.io diagrams in [`DIAGRAMS.md`](DIAGRAMS.md).
