# ADR-005: Sync for reserve/authorize, async for order/shipment/notification
**Status:** Accepted
**Context:** User needs instant answers for stock and payment; downstream services can fail.
**Decision:** Reserve and authorize are synchronous with tight timeouts. Order creation, capture, shipment, notifications and cache invalidation are asynchronous via outbox + Kafka.
**Alternatives:** Fully synchronous chain (simple, but Order outage fails the purchase); fully async including reserve (resilient but user waits/polls for stock answer).
**Consequences:** + Order outage doesn't lose purchases; user gets immediate stock/payment answer. − Eventual consistency for order status; need idempotent consumers, DLQ, reconciliation.
