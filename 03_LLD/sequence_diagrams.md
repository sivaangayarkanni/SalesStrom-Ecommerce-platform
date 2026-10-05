# 03 – Sequence Diagrams

## 1. Purchase / reservation (shows which cache tier answers)
```mermaid
sequenceDiagram
  participant U as Customer
  participant CDN as L1 CDN
  participant GW as API Gateway
  participant RC as ReservationController
  participant L2 as L2 SoldOutFlag
  participant R as L3 Redis
  participant DB as L4 Postgres
  U->>CDN: POST /sales/42/reservations (Idempotency-Key)
  alt SOLD_OUT flag cached at edge
    CDN-->>U: 409 SOLD_OUT (answered at L1)
  else
    CDN->>GW: forward
    GW->>GW: verify JWT, rate limit
    GW->>RC: reserve
    RC->>L2: isSoldOut?
    alt sold out locally
      L2-->>U: 409 SOLD_OUT (answered at L2)
    else
      RC->>R: idempotency key seen?
      alt seen
        R-->>U: replay stored response (answered at L3)
      else
        RC->>R: tryAcquire token (Lua atomic)
        alt no token
          R-->>U: 409 SOLD_OUT and publish StockSoldOut
        else token
          RC->>DB: BEGIN, claim unit SKIP LOCKED, insert reservation, outbox, COMMIT
          DB-->>RC: reservation id, expires_at
          RC->>R: store response under idempotency key
          RC-->>U: 201 RESERVED (only YES comes from L4)
        end
      end
    end
  end
```

## 2. Payment (success, decline, timeout, duplicate)
See `payment_order_design.md` section 2 for the full alt-block diagram. Duplicate path:
```mermaid
sequenceDiagram
  participant U as Customer
  participant P as Payment Service
  participant DB as Postgres
  participant G as Gateway
  U->>P: POST /payments key K
  P->>DB: INSERT payment key K
  P->>G: authorize key K
  U->>P: POST /payments key K again (retry)
  P->>DB: INSERT payment key K
  DB-->>P: unique violation
  P-->>U: replay first result, no second gateway call
  G-->>P: authorized
```

## 3. Order creation and recovery
```mermaid
sequenceDiagram
  participant K as Kafka
  participant O as Order Service
  participant DB as Postgres
  participant P as Payment Service
  participant N as Notification
  K->>O: PaymentAuthorized
  O->>DB: INSERT order UNIQUE payment_id, outbox OrderCreated
  alt duplicate delivery
    DB-->>O: unique violation, ack and skip
  end
  DB->>K: OrderCreated
  K->>P: capture
  P->>DB: CAPTURED, outbox PaymentCaptured
  K->>O: PaymentCaptured, order CONFIRMED
  K->>N: OrderConfirmed, send email and SMS
```
Recovery from a 30 s Order outage: `payment_order_design.md` section 4.
