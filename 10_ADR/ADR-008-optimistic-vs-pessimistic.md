# ADR-008: Pessimistic (SKIP LOCKED) for stock, optimistic for everything else
**Status:** Accepted
**Context:** Contention differs: stock is extremely contended for seconds; orders/carts are rarely updated concurrently.
**Decision:** Stock: row locks with SKIP LOCKED (no waiting). Orders, carts, payments: optimistic `version` checks.
**Alternatives:** Optimistic everywhere (retry storm on stock); pessimistic everywhere (unnecessary lock waits).
**Consequences:** + Right tool per contention level. − Two concurrency styles for the team to understand.
