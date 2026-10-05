# 09 – Security & Observability Design

## Security
| Requirement | Design |
|---|---|
| Authentication | OAuth2/OIDC login, short-lived JWT (15 min) + refresh token; validated at API Gateway |
| Authorization | Role/ownership checks in services (customer can only read own reservation/order); admin APIs separate, MFA |
| Transport | HTTPS/TLS 1.2+ at edge; mTLS between services (service mesh) |
| Rate limiting & abuse | WAF bot detection, per-IP and per-user limits (e.g. 1 Buy / 2 s), CAPTCHA in waiting room for suspicious clients, one unit per customer (DB unique) |
| Input validation | Schema validation at gateway + DTO validation; parameterized SQL only; max body size |
| Payment data | **Never store card data.** Client-side tokenization by gateway (PCI DSS scope reduced); store only token + `provider_txn_ref`; webhooks verified by HMAC signature + timestamp |
| Secrets | Vault / cloud secrets manager, rotated; never in code or images |
| Audit | Append-only `audit_log` (who, what, before/after, traceId) for reservation, payment, order changes; logs shipped to tamper-evident storage |
| Idempotency keys | Bound to user (key + user id) so one user can't replay another's key |

## Observability
### Key metrics
| Metric | Why |
|---|---|
| Request rate, latency p50/p95/p99, error rate per endpoint | Golden signals |
| **Cache hit ratio per ladder tier (L1, L2, L3)** and requests reaching DB | Proves our unique factor; alert if DB share rises |
| Tokens remaining vs `available` | Detect drift |
| Reservation success / SOLD_OUT / ALREADY_RESERVED / expiry counts | Business health |
| Payment authorize success/fail/timeout rate, breaker state | Gateway health |
| Retry ratio (retries / calls) vs 10% budget; shed (503) rate | Early warning of a retry storm / metastable state |
| Per-endpoint phi (suspicion) and ejected-host count | Gray failure detection |
| Inbox hit rate (duplicates skipped) per consumer | Shows redelivery volume; should be small |
| Lease holder + fence token changes | Leader churn on sweeper / relay |
| Watermark lag and `reconciliation_case` OPEN count | Late events waiting for void/refund |
| Latency as HdrHistogram from intended start (load tests) | No coordinated omission |
| Order conversion (reserved → sold) | Business KPI |
| Kafka consumer lag, DLQ size, outbox unpublished count | Async health |
| DB lock wait time, connection pool usage | Bottleneck detection |

### Structured log example (JSON)
```json
{"ts":"2026-10-05T10:00:00.412+05:30","level":"INFO","service":"inventory",
 "event":"RESERVATION_CREATED","traceId":"4bf92f35","saleId":42,"customerId":"c-9912",
 "reservationId":"r-81f3","unitId":57,"tier":"L4","latencyMs":14,"idempotencyKey":"7b1e..."}
```
```json
{"ts":"2026-10-05T10:00:01.020+05:30","level":"WARN","service":"payment",
 "event":"PAYMENT_TIMEOUT","traceId":"9c1d","paymentId":"p-33","provider":"razorpay","action":"RECONCILE_SCHEDULED"}
```

### Distributed tracing
OpenTelemetry trace from gateway → reservation → checkout → payment → (Kafka headers carry `traceparent`) → order → capture → notification. One `traceId` returned in every error response, so support can follow one purchase end-to-end.

### Alerts
| Alert | Condition | Severity |
|---|---|---|
| **Inventory invariant violation** | `available+reserved+sold ≠ total` or sold > total | Page immediately |
| Token drift | Redis tokens ≠ DB available for > 30 s | High |
| Payment failure spike | Fail rate > 10% for 1 min or breaker open | High |
| Authorized without order | Any older than 15 min | High |
| Queue backlog | Consumer lag > 10k or DLQ > 0 | Medium |
| Cache hit drop | L1+L2 hit ratio < 90% during sale | Medium |
| Latency | Reserve p99 > 200 ms for 2 min | Medium |

> **Defend it**
> - "We never touch card numbers – the gateway tokenizes them, which keeps us mostly out of PCI scope."
> - "Our dashboard shows hit ratio per cache tier, so we can prove the ladder is working during the sale."
