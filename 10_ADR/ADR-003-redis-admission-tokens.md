# ADR-003: Redis token pool as admission control
**Status:** Accepted
**Context:** Even with SKIP LOCKED, sending 10,000 transactions to the DB wastes connections.
**Decision:** Load exactly N tokens (N = available units) into Redis; atomic pop (Lua) admits a request to the DB; tokens returned on release; local SOLD_OUT flag once empty.
**Alternatives:** DB only (correct, but 10k transactions); queue all requests in Kafka and process serially (fair, but slow response and complex UX).
**Consequences:** + ~100 DB transactions; ~1 ms rejection. − Token drift possible (crash after pop) ⇒ reconciliation job re-syncs tokens with DB. Correctness never depends on Redis.
