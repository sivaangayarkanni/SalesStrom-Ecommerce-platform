# ADR-002: Inventory as unit rows claimed with SKIP LOCKED
**Status:** Accepted
**Context:** Many concurrent buyers for a small stock; a single counter row becomes a hot lock.
**Decision:** One row per unit in `inventory_unit`; claim with `SELECT … FOR UPDATE SKIP LOCKED LIMIT 1` inside the reservation transaction; aggregate counters updated with CHECK constraints.
**Alternatives:** Pessimistic lock on counter (serializes everything); optimistic `version` (retry storms); conditional `UPDATE … WHERE available >= 1` (good, kept as Redis-down fallback); Redis-only DECR (not durable).
**Consequences:** + No waiting, deterministic last unit, audit per unit. − 100 rows per sale item; for very large stock switch to sharded counters.
