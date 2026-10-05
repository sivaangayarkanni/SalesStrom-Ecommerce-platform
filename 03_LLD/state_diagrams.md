# 03 – State Diagrams

![state_reservation](drawio/state_reservation.png)

*Editable source: [`drawio/state_reservation.drawio`](drawio/state_reservation.drawio) — open in [app.diagrams.net](https://app.diagrams.net).*

![state_order](drawio/state_order.png)

*Editable source: [`drawio/state_order.drawio`](drawio/state_order.drawio) — open in [app.diagrams.net](https://app.diagrams.net).*


## Reservation lifecycle
```mermaid
stateDiagram-v2
  [*] --> AVAILABLE
  AVAILABLE --> RESERVED: unit claimed
  RESERVED --> PAYMENT_PENDING: checkout started
  PAYMENT_PENDING --> CONFIRMED: payment authorized, fencing ok
  CONFIRMED --> SOLD: order persisted and captured
  RESERVED --> TIMEOUT: expires_at reached
  PAYMENT_PENDING --> PAYMENT_FAILED: declined or voided
  TIMEOUT --> RELEASED
  PAYMENT_FAILED --> RELEASED
  RELEASED --> AVAILABLE: unit freed, token returned, StockReleased
  SOLD --> [*]
```
Note: PAYMENT_PENDING does not time out while an authorization is held; it is extended and resolved by reconciliation.

## Order lifecycle
```mermaid
stateDiagram-v2
  [*] --> CREATED
  CREATED --> PAYMENT_PENDING
  PAYMENT_PENDING --> CONFIRMED: captured
  PAYMENT_PENDING --> CANCELLED: failed or voided
  CONFIRMED --> PROCESSING
  PROCESSING --> SHIPPED
  SHIPPED --> OUT_FOR_DELIVERY
  OUT_FOR_DELIVERY --> DELIVERED
  CONFIRMED --> CANCELLED: customer cancel
  PROCESSING --> CANCELLED: customer cancel
  CANCELLED --> REFUNDED: if captured
  DELIVERED --> [*]
  REFUNDED --> [*]
```
