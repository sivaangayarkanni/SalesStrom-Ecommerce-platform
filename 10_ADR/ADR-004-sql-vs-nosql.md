# ADR-004: PostgreSQL (SQL) for inventory, payments and orders
**Status:** Accepted
**Context:** Stock and money need atomic multi-row updates and constraints.
**Decision:** PostgreSQL as system of record; Redis for cache/admission; Kafka for events. Catalog can use read replicas (or a document store later).
**Alternatives:** DynamoDB/Cassandra – scale well, but conditional writes are per-item, no multi-table transactions/CHECK constraints across reservation + unit + outbox; MongoDB transactions possible but weaker team familiarity.
**Consequences:** + ACID, constraints, SKIP LOCKED, outbox in same transaction. − Vertical write limit ⇒ partition/shard at very large scale (writes are bounded by stock here).
