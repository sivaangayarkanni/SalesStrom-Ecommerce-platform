# 05 – API & Event Specification

All APIs: HTTPS, `Authorization: Bearer <JWT>` (except public catalog reads), JSON, error body `{ "code", "message", "traceId" }`. Writes that create business transactions **require `Idempotency-Key`** (UUID). Full machine-readable spec: `05_API/tools/openapi.yaml` (if present).

## REST endpoints
| Method | Path | Auth | Request | Success | Errors | Cache (ladder tier) |
|---|---|---|---|---|---|---|
| GET | `/products/{id}` | public | – | 200 product | 404 | L1 CDN `max-age=300`, ETag; L2 |
| GET | `/sales/{saleId}` | public | – | 200 sale config, start/end | 404 | L1 `max-age=60`; L2 |
| GET | `/sales/{saleId}/stock-status` | public | – | 200 `{status: IN_STOCK\|SOLD_OUT}` | – | L1 `max-age=1`, purged on `StockSoldOut`/`StockReleased` |
| POST | `/carts/{cartId}/items` | JWT | `{productId, qty}` | 200 cart | 400, 404 | none (Redis-backed) |
| POST | `/sales/{saleId}/reservations` | JWT | `{productId}` + `Idempotency-Key` | **201** `{reservationId, expiresAt}`; **200** replay | **409 SOLD_OUT**, **409 ALREADY_RESERVED**, 400, 401, **429** rate limited, **503** waiting room + `Retry-After` | NO answers may come from L1/L2/L3; YES only from DB |
| GET | `/reservations/{id}` | JWT (owner) | – | 200 status, expiresAt | 404 | none |
| DELETE | `/reservations/{id}` | JWT (owner) | – | 204 released | 404, 409 already paid | none |
| POST | `/checkout` | JWT | `{reservationId, couponCode?, paymentMethod}` + `Idempotency-Key` | 200 `{checkoutId, amount}` | 409 reservation expired, 422 invalid coupon | none |
| POST | `/payments` | JWT | `{checkoutId, paymentToken}` + `Idempotency-Key` | **202** `{paymentId, status: AUTHORIZED\|PENDING}` | 402 declined, 409 duplicate in progress, 503 gateway unavailable (breaker open) | none |
| POST | `/payments/webhook` | gateway HMAC signature | gateway event | 200 | 401 bad signature | none |
| GET | `/orders/{id}` | JWT (owner) | – | 200 order + state | 404 | none |
| POST | `/orders/{id}/cancel` | JWT (owner) | `Idempotency-Key` | 202 cancelling | 409 already shipped | none |
| GET | `/shipments/{id}/tracking` | JWT (owner) | – | 200 tracking events | 404 | L2 30 s |

### Example: reserve
```http
POST /sales/42/reservations
Authorization: Bearer eyJ...
Idempotency-Key: 7b1e0c9a-5c1d-4f7e-9a51-2f1f2a9c3d10
{ "productId": "X" }

201 Created
{ "reservationId": "r-81f3", "status": "RESERVED", "expiresAt": "2026-10-05T10:05:00+05:30" }

409 Conflict
{ "code": "SOLD_OUT", "message": "All units have been reserved", "traceId": "4bf92f35" }
```

## Commands vs events
| Name | Type | Owner (producer) | Consumers |
|---|---|---|---|
| ReserveUnit | Command (sync API) | Checkout → Inventory | – |
| AuthorizePayment | Command (sync API) | Checkout → Payment | – |
| CapturePayment / VoidPayment | Command (async) | Checkout saga | Payment |
| ReservationCreated | Event | Inventory | Checkout saga, analytics |
| ReservationExpired / ReservationReleased | Event | Inventory | Checkout saga, Cache Invalidator |
| StockSoldOut | Event | Inventory | **Cache Invalidator → CDN flag + all pods' L2 flag** |
| StockReleased | Event | Inventory | Cache Invalidator (clears SOLD_OUT) |
| PaymentAuthorized | Event | Payment | Order, Inventory (extend), saga |
| PaymentFailed | Event | Payment | Inventory (release), Notification, saga |
| PaymentCaptured / PaymentVoided | Event | Payment | Order, Inventory, Notification |
| OrderCreated / OrderConfirmed / OrderCancelled | Event | Order | Payment (capture/refund), Shipment, Notification |
| ShipmentCreated / ShipmentStatusChanged | Event | Shipment | Order, Notification |

Rules: the **owner** is the only service that writes that data and publishes the event; events published via **outbox** (at-least-once); every consumer is **idempotent** (dedupe by `event_id`), retries 5× then **DLQ**. Kafka key = aggregate id (reservation/order id) so events for one entity stay ordered.

> **Defend it**
> - "Only creating business transactions needs Idempotency-Key; reads are cached at the ladder tiers."
> - "Each event has one owner; consumers are idempotent because delivery is at-least-once."
