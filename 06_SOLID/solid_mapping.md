# 06 – SOLID Mapping

| Principle | Where in our design | How it shows |
|---|---|---|
| **SRP** – one reason to change | `ReservationService` (stock only), `PaymentService` (money only), `OrderService` (order lifecycle only), `NotificationObserver` (messages only), `SoldOutFlag` (cache flag only) | A change to SMS templates never touches payment code |
| **OCP** – open for extension, closed for change | `PricingStrategy` (FlashSalePricing, CouponPricing), `PaymentGateway` adapters, `DeliveryPartnerAdapter`, `OrderObserver` | New provider/strategy = new class + registration; core classes unchanged |
| **LSP** – subtypes substitutable | Any `PaymentGateway` (Razorpay, Stripe, CircuitBreakerGateway decorator) honours the same contract: idempotent with same key, returns `GatewayResult`, never throws for declines | `PaymentService` works the same with any of them |
| **ISP** – small focused interfaces | `TokenPool` (acquire/release), `IdempotencyStore`, `InventoryUnitRepository`, `OrderObserver` (one method) – instead of one giant `InventoryManager` | Notification code doesn't depend on payment methods |
| **DIP** – depend on abstractions | `ReservationService` depends on `TokenPool` and `InventoryUnitRepository`, not Redis/Postgres; `PaymentService` depends on `PaymentGateway`, not Razorpay SDK | Redis can be replaced, or mocked in tests; DB fallback path is just another `TokenPool` that always admits |

**DIP + our unique factor:** each Cache-Hit Ladder tier is an interface (`SoldOutFlag`, `TokenPool`, `IdempotencyStore`), so when Redis is down we inject a `DbFallbackTokenPool` and the system keeps running – slower but correct.

> **Defend it**
> - "SRP is why an Order Service crash doesn't touch stock or money – they're separate classes and services."
> - "DIP lets us swap Redis for a DB fallback at runtime without changing ReservationService."
