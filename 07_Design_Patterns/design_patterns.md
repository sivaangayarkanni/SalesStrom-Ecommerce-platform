# 07 – Design Pattern Mapping

| Pattern | Where | Problem solved | Trade-off |
|---|---|---|---|
| **Strategy** | `PricingStrategy` (flash price, coupon, bulk); provider selection | Pricing rules change every sale without editing checkout | More classes; needs config to pick a strategy |
| **Factory** | `PaymentProviderFactory.forMethod(method, region)` | Hides which gateway object is built (and breaker-wrapped) | Factory must be updated/registered for new providers |
| **State** | `OrderState` classes; `Reservation` status methods | Illegal transitions (DELIVERED → PROCESSING) impossible by construction | One class per state; more files |
| **Observer** | `OrderEventPublisher` → Notification, Shipment observers; Kafka consumers at service level | Order doesn't need to know who reacts to its events | Harder to trace flow; needs tracing IDs |
| **Adapter** | `RazorpayAdapter`, `StripeAdapter`, `DeliveryPartnerAdapter` | Different external APIs behind one interface | Lowest-common-denominator API; adapter maintenance |
| **Repository** | `InventoryUnitRepository`, `ReservationRepository`, `PaymentRepository` | Business code free of SQL; easy to test | Complex queries (SKIP LOCKED) still need custom SQL inside |
| **Facade** | `CheckoutFacade` | One simple call hides reserve → price → authorize → saga | Facade can grow too big; keep it thin, logic in saga |
| **Circuit Breaker** | `CircuitBreakerGateway` (Decorator around gateway) | Stops hammering a failing gateway; fails fast | Some requests rejected while open even if gateway recovered |
| **Saga (orchestration)** | `CheckoutSaga` | Distributed workflow with compensations (void, release) | Eventual consistency; saga state to store |
| **Transactional Outbox** | `OutboxWriter` + relay | No lost events between DB commit and Kafka | Extra table + relay process; at-least-once ⇒ idempotent consumers |
| **Cache-Aside + Write-Invalidate** | L2/L3 caches, `SoldOutFlag` | Low latency reads, fast NO answers | Short staleness window (only ever errs on the side of NO) |
| **Decorator** | `CircuitBreakerGateway`, metrics wrapper | Add resilience/metrics without changing adapters | Layers of wrapping |

## Adding something new with minimal change
**New payment provider (e.g. PayU):**
```java
class PayUAdapter implements PaymentGateway {
  public GatewayResult authorize(AuthRequest r, String key) { /* call PayU */ }
  public GatewayResult capture(String ref, String key) { ... }
  public GatewayResult voidAuth(String ref) { ... }
  public GatewayResult status(String key) { ... }
}
// register: factory.register("PAYU", () -> new CircuitBreakerGateway(new PayUAdapter(), breaker));
```
No change to `PaymentService`, `CheckoutSaga`, or `OrderService`.

**New pricing strategy (e.g. first-100-buyers discount):** `class EarlyBirdPricing implements PricingStrategy` + sale config `pricing=EARLY_BIRD`.

**New delivery partner (e.g. Delhivery):** `class DelhiveryAdapter implements DeliveryPartnerAdapter` + register by pincode region.

> **Defend it**
> - "Adding PayU is one new adapter class and one registration line – that's OCP via Strategy + Factory + Adapter."
> - "State pattern makes illegal order transitions impossible to code by accident."
