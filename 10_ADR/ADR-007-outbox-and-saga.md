# ADR-007: Transactional outbox + orchestrated saga
**Status:** Accepted
**Context:** Writing to DB and publishing to Kafka separately can lose events (dual-write problem).
**Decision:** Write events to `outbox_event` in the same transaction as the state change; relay publishes to Kafka. Checkout Orchestrator runs the saga (reserve → authorize → order → capture) with compensations (release, void).
**Alternatives:** Dual write (can lose events); 2PC/XA (blocking, poor availability); choreography only (hard to see/control the flow).
**Consequences:** + No lost events, clear compensations. − At-least-once delivery ⇒ idempotent consumers; extra relay process and saga state table.
