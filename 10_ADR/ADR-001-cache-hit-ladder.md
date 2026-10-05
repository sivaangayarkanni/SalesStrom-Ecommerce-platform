# ADR-001: Cache-Hit Ladder for latency and load
**Status:** Accepted
**Context:** 10,000 Buy clicks for 100 units; 99% must fail. Up to 500k req/s. Origin and DB cannot absorb this directly.
**Decision:** Answer each request at the cheapest correct tier: L0 browser, L1 CDN (pages + SOLD_OUT flag), L2 in-process cache, L3 Redis (tokens, idempotency), L4 Postgres. Caches may answer reads and NO; only the DB answers YES. Invalidation by events (outbox → CDN purge + pub/sub), TTL with jitter as safety net.
**Alternatives:** (a) Single Redis cache in front of DB – still sends all traffic to origin. (b) No caching, scale DB – expensive, hot-row contention remains. (c) Cache stock counts and sell from cache – fast but can oversell.
**Consequences:** + Very low latency, DB sees ~105 writes, 50× traffic mostly absorbed at edge. − More moving parts; brief staleness (only ever errs toward SOLD_OUT); need cache-invalidation pipeline and per-tier monitoring.
