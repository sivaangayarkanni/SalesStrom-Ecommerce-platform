# AI Usage Note

**Tool used:** Grok Bot (AI assistant).

**Design first:** the team chose the architecture – the Cache-Hit Ladder, unit-row inventory with SKIP LOCKED, the Redis token pool, authorize-then-capture, outbox + saga – before generating any artefacts. AI was used to speed up writing and checking.

| Artefact | AI used for | How we validated it |
|---|---|---|
| Markdown docs and Mermaid diagrams | Drafting text and diagram code from our decisions | Reviewed by every team member; diagrams rendered in Mermaid Live |
| `schema_postgres.sql`, `schema_mysql.sql`, `.dbml` | Boilerplate DDL from our ER design | Checked constraints match guarantees G1–G5 |
| `openapi.yaml`, Postman collection | API skeletons from our endpoint table | Opened in Swagger Editor / Postman import |
| `simulate.py` | Simulation script of our design | Ran it: 100 sold, 0 invariant violations; naive mode oversold (650) – the control proves the checks work. We fixed the Order-outage window after the first run showed it didn't overlap the payments |
| Locust / JMeter scripts | Load-test boilerplate | Syntax checked; target endpoints match the API spec |

**Prompt summary:** "Given our design decisions [listed], write requirements, HLD/LLD docs, Mermaid diagrams, SQL schema, OpenAPI spec and a simulation of 10,000 users / 100 units with 5% payment failures, 2% duplicates and a 30 s Order Service outage, checking the inventory invariant after every step."

Every team member can explain every file.
