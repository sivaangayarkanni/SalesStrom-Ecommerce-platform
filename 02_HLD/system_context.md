# 02 – System Context Diagram

```mermaid
flowchart LR
  C([Customer]) -->|HTTPS| EDGE[CDN + WAF]
  EDGE --> S[SALESTORM Platform]
  OPS([Ops and Support]) -->|Admin dashboard| S
  S -->|Authorize, capture, void, refund| PG[Payment Gateway]
  PG -->|Signed webhooks| S
  S -->|Create shipment, tracking| LP[Logistics Partner]
  S -->|SMS, Email, Push| NP[Notification Providers]
  S -->|Metrics, logs, traces| OBS[Monitoring Stack]
```

| Actor / System | Why it is outside our boundary |
|---|---|
| Customer | Browses and buys; untrusted input |
| CDN + WAF | Edge tier **L1** of the Cache-Hit Ladder; absorbs most traffic and bots |
| Payment Gateway | External, can be slow or fail ⇒ wrapped by Adapter + Circuit Breaker |
| Logistics Partner | External delivery; wrapped by DeliveryPartnerAdapter |
| Notification Providers | External SMS/email/push; async only |
| Ops | Monitors sale, handles refunds and reconciliation |

> **Defend it**
> - "Every external system sits behind an adapter, so a slow partner can never block a stock decision."
> - "The CDN is part of our design, not just hosting – it is tier L1 of our cache ladder."
