# Team Ownership: who prepares what

Every member may be asked about any module, so each person should also skim `00_Unique_Value_Proposition.md`, `README.md` and the [live site](https://sivaangayarkanni.github.io/SalesStrom-Ecommerce-platform/).

## Student 1: System Architect (HLD, architecture, scalability, deployment)
| Folder / file | What to prepare |
|---|---|
| `01_Requirements/` | Functional vs non-functional requirements, hard guarantees (exactly 100 sold, no double charge) vs targets (latency, RPS) |
| `00_Unique_Value_Proposition.md` | Explain the Cache-Hit Ladder L0 to L4 and "Caches can say NO. Only the database can say YES." |
| `02_HLD/` | system_context, hld_architecture, container, component, deployment diagrams (`drawio/`), and walk through the request path end to end |
| `08_Scalability_Reliability/` | 500k req/s peak absorbed at CDN/L1, horizontal scaling, Little's law sizing, <70% utilisation |
| `10_ADR/` ADR-001, 003, 004, 005, 010 | Cache-Hit Ladder, Redis admission tokens, SQL vs NoSQL, sync vs async, cell isolation |
| `12_Presentation/` | Lead the pitch: opening, architecture slide, timeline answer |

Be ready for: "Why not just add more servers?", "What happens at 500k req/s?", "Why a separate flash-sale cell?"

## Student 2: LLD & Design Engineer (LLD, SOLID, UML, design patterns)
| Folder / file | What to prepare |
|---|---|
| `03_LLD/class_diagrams.md` + `drawio/class_diagram` | Every class and its responsibility, including the new resilience classes (RetryBudget, BackoffWithJitter, LoadShedder, SingleflightCache, HotKeySaltedTokenPool, LeaseManager/FencingToken, InboxDeduplicator, PhiAccrualDetector) |
| `03_LLD/sequence_diagrams.md` + `seq_*` | Reservation, payment and order-recovery sequences step by step |
| `03_LLD/state_diagrams.md` + `state_*` | Reservation and order state machines, every transition |
| `06_SOLID/` | One concrete SALESTORM example per SOLID principle |
| `07_Design_Patterns/` | Facade, Saga, Strategy (pricing), Factory + Adapter (payment), Circuit Breaker, Outbox; why each was chosen |
| `14_Diagram_Screenshots/` | Know which diagram shows what |

Be ready for: "Which pattern handles payment provider switching?", "Show where Open/Closed applies", "Walk the reservation sequence."

## Student 3: Data & API Engineer (database, APIs, events, integration)
| Folder / file | What to prepare |
|---|---|
| `04_Database/database_design.md` + `drawio/er_diagram` | All 22 tables, keys, constraints, why per-unit inventory rows |
| `04_Database/tools/` | `schema_postgres.sql` (main), `schema_mysql.sql` (Workbench), `salestorm.dbml` (dbdiagram.io), `resilience_checks.sql` |
| `05_API/api_specification.md` + `tools/openapi.yaml`, Postman collection | Endpoints, Idempotency-Key header, error codes (409 sold out, 503 + Retry-After); demo on the [Swagger page](https://sivaangayarkanni.github.io/SalesStrom-Ecommerce-platform/api.html) |
| `03_LLD/payment_order_design.md` | Authorize then capture, payment webhooks, reconciliation |
| `10_ADR/` ADR-004, 006, 007 | SQL vs NoSQL, authorize-then-capture, outbox + saga |
| Events | Outbox table, Kafka topics, inbox_message dedupe at Order/Shipment/Notification, event time vs processing time + watermark |

Be ready for: "How do you stop a duplicate order?", "SQL or NoSQL and why?", "What if the payment webhook arrives late?"

## Student 4: Reliability Engineer (concurrency, failure handling, security, recovery)
| Folder / file | What to prepare |
|---|---|
| `03_LLD/concurrency_inventory_design.md` + `drawio/concurrency_flow` | SELECT ... FOR UPDATE SKIP LOCKED, why oversell is write skew, CHECK + unique index |
| `02_HLD/Production_Failure_Modes.md` | All 14 failure modes: the failure, the control, the one-line answer |
| `10_ADR/` ADR-002, 008, 009 | Unit rows + SKIP LOCKED, optimistic vs pessimistic, resilience controls |
| `09_Security_Observability/` | JWT, rate limiting, WAF, bot protection, metrics/logs/traces |
| `11_AI_Assisted_Validation/` | Simulation results (100 sold, 0 oversell, retry storm, 30 s Order outage = 0 duplicates, fencing token), open-loop Locust/JMeter |
| Recovery | 30 s Order Service outage walkthrough: outbox keeps events, inbox dedupes, sweeper with fencing token releases expired holds |

Be ready for: "Two users click Buy for the last unit at the same instant?", "Order Service is down for 30 seconds, what happens?", "Payment succeeds but order creation fails?"

## If the team has only 3 members
Split Student 4 between the others: Student 1 takes failure modes, security and observability (`02_HLD/Production_Failure_Modes.md`, `09_Security_Observability/`), Student 2 takes concurrency (`concurrency_inventory_design.md`, ADR-002/008), and Student 3 takes recovery and validation (outbox/inbox, `11_AI_Assisted_Validation/`).
