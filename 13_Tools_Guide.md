# Tools guide — which file to open where

Every tool named in the hackathon brief has a matching artifact in this repo.

| Tool | File(s) | How to open |
|------|---------|-------------|
| **Draw.io / diagrams.net** | All 14 diagrams (incl. `02_HLD/drawio/resilience_controls.drawio`): `02_HLD/drawio/*.drawio`, `03_LLD/drawio/*.drawio`, `04_Database/drawio/er_diagram.drawio` (+ PNG exports) | [app.diagrams.net](https://app.diagrams.net/) → Open Existing Diagram |
| **PlantUML** | `02_HLD/tools/*.puml`, `03_LLD/tools/*.puml` (alternate source) | VS Code PlantUML extension, or `plantuml -tpng file.puml` |
| **Mermaid** | Embedded in `02_HLD/*.md`, `03_LLD/*.md` | GitHub renders them; or [mermaid.live](https://mermaid.live) |
| **StarUML** | Import via PNG / or recreate from `03_LLD/tools/class_diagram.puml` | Open StarUML → File → Import → Image, or redraw from PlantUML |
| **Visual Paradigm** | Same PlantUML / PNG sources under `02_HLD/tools` and `03_LLD/tools` | Import PNG or export from PlantUML to XMI if needed |
| **MySQL Workbench** | `04_Database/tools/schema_mysql.sql` | Server → Data Import → Import from Self-Contained File |
| **dbdiagram.io** | `04_Database/tools/salestorm.dbml` | Paste into [dbdiagram.io](https://dbdiagram.io) |
| **Swagger / OpenAPI** | `05_API/tools/openapi.yaml` | [editor.swagger.io](https://editor.swagger.io) or Redocly |
| **Postman** | `05_API/tools/salestorm.postman_collection.json` | Import → File |
| **GitHub** | This repository | Clone and browse |
| **JMeter** | `11_AI_Assisted_Validation/load_tests/salestorm_flash_sale.jmx` (open-loop: Precise Throughput Timer, 10,000 req/s) | File → Open in Apache JMeter; `jmeter -n -t salestorm_flash_sale.jmx -Jthreads=5000 -Jduration=65` |
| **Locust** | `11_AI_Assisted_Validation/load_tests/locustfile.py` (open-loop Poisson arrivals, intended-start latency) | `TARGET_RPS=10000 locust -f locustfile.py --headless -u 200 -r 200 --run-time 70s --host …` |

## Validated locally

- Postgres schema: applied to a temp Postgres 17 cluster — **22 tables** created cleanly; `resilience_checks.sql` passes (fencing, inbox, write skew, oversell CHECK).  
- DBML: parsed with `@dbml/core` — 22 tables.  
- OpenAPI: Redocly lint — **valid** (warnings only).  
- PlantUML diagrams: all rendered to PNG.  
- Locust file: Python compile OK (not run against a live target).  
- JMeter `.jmx`: well-formed XML.  
- Simulation: **PASS** (see `11_AI_Assisted_Validation/simulation/results.json`); resilience scenarios **PASS** (`resilience_output.txt`).

## Quick index

See **[DIAGRAMS.md](DIAGRAMS.md)** for every PNG / Draw.io / PlantUML / Mermaid source file.

