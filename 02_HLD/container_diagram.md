# 02 – Container / Service Diagram

```mermaid
flowchart TB
  subgraph Edge
    CDN[CDN and WAF]
    LB[Load Balancer]
    GW[API Gateway]
  end
  subgraph Services
    PS[Product and Sale Service]
    CS[Cart Service]
    WR[Waiting Room]
    CK[Checkout Orchestrator]
    INV[Inventory and Reservation Service]
    PAY[Payment Service]
    ORD[Order Service]
    SH[Shipment Service]
    NT[Notification Service]
    RC[Reconciliation Worker]
  end
  subgraph Data
    R[(Redis Cluster)]
    DB[(Postgres Primary)]
    RR[(Read Replicas)]
    K[[Kafka]]
  end
  subgraph External
    PGW[Payment Gateway]
    LP[Logistics Partner]
    NP[SMS Email Push]
  end
  CDN --> LB --> GW
  GW --> PS
  GW --> CS
  GW --> WR --> CK
  CK -->|sync REST| INV
  CK -->|sync REST| PAY
  PS --> RR
  CS --> R
  INV --> R
  INV --> DB
  PAY --> DB
  PAY --> PGW
  DB -.outbox.-> K
  K -.-> ORD
  K -.-> SH
  K -.-> NT
  K -.-> RC
  ORD --> DB
  SH --> LP
  NT --> NP
```
Solid arrows = synchronous; dotted = asynchronous events.

| Container | Tech (proposed) | Owns data |
|---|---|---|
| Product & Sale | Spring Boot/Node + Caffeine (L2) | product, category, sale, deal, coupon |
| Cart | Service + Redis | cart, cart_item |
| Inventory & Reservation | Service + Redis tokens + Postgres | inventory, inventory_unit, inventory_reservation |
| Payment | Service + Postgres | payment, idempotency_record |
| Order | Service + Postgres | orders, order_item |
| Shipment / Notification | Services | shipment, notification |
| Checkout Orchestrator | Stateless + saga state table | saga log |

> **Defend it**
> - "Each service owns its own tables – no shared writes, so boundaries stay clean."
> - "Only two sync hops on the critical path: reserve and authorize."
