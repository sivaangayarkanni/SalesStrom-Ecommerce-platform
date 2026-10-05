# 02 – Component Diagram (critical services)

## Inventory & Reservation Service
```mermaid
flowchart TB
  API[ReservationController] --> V[RequestValidator]
  V --> IDEM[IdempotencyGuard - Redis then DB]
  IDEM --> SOF[SoldOutFlag - L2 local boolean]
  SOF --> TP[TokenPool - Redis Lua atomic pop]
  TP --> RS[ReservationService]
  RS --> UR[InventoryUnitRepository - SKIP LOCKED claim]
  RS --> RR[ReservationRepository]
  RS --> OBW[OutboxWriter - same transaction]
  EXP[ExpiryScheduler - delayed queue plus sweeper] --> RS
  OBW --> DB[(Postgres)]
  UR --> DB
  RR --> DB
  TP --> R[(Redis)]
  IDEM --> R
```

## Checkout Orchestrator
```mermaid
flowchart TB
  CF[CheckoutFacade] --> SAGA[CheckoutSaga - state machine]
  SAGA --> IC[InventoryClient]
  SAGA --> PC[PaymentClient]
  SAGA --> PR[PricingStrategy]
  SAGA --> CB[CircuitBreaker]
  SAGA --> COMP[CompensationHandler - release unit, void auth]
  SAGA --> LOG[(Saga log table)]
```

| Component | Responsibility |
|---|---|
| IdempotencyGuard | Replays the stored response for a repeated key; blocks duplicate business work |
| SoldOutFlag | Local boolean flipped by `StockSoldOut` event – zero network cost "NO" |
| TokenPool | Atomic admission: 100 tokens, one per successful entrant |
| ReservationService | Transaction: claim unit row, insert reservation, write outbox event |
| ExpiryScheduler | Releases expired reservations (delayed queue, with periodic sweeper as fallback) |
| CheckoutSaga | Orders steps: reserve → authorize → (async) order → capture; triggers compensations |

> **Defend it**
> - "Validation and idempotency happen *before* we touch stock, so duplicates never cost a lock."
> - "The outbox row is written in the same transaction as the reservation – no event is ever lost."
