# Simulation – evidence for the design

Run: `python3 simulate.py` (safe design) and `python3 simulate.py --naive` (no locking, negative control). Python 3 standard library only. Time is scaled (1 simulated second = 10 ms).

**Scenario from the brief:** 10,000 users, 100 units, payment 95% success / 5% failure, 2% duplicate requests, Order Service down for 30 (simulated) seconds.

| Check | Design claim it validates |
|---|---|
| Requests answered per tier (L1 CDN flag, L2 local flag, L3 pool, replay, DB) | Cache-Hit Ladder: most requests never reach the DB |
| `reached_db` ≈ 100 + failed-payment resales | Token pool bounds DB writes by stock, not traffic |
| `available + reserved + sold == 100` after every operation, `sold <= 100`, never negative | No overselling (G1) |
| Duplicates collapsed, none reached DB twice | Idempotency + one reservation per customer (G2) |
| Max charges per customer = 1 | No double charge (G3) |
| Orders created after outage = paid orders; captured = orders | Outbox + authorize-then-capture (G4) |
| Failed payments → unit released → resold | Reservation release path |
| `--naive` mode oversells | Shows *why* the locking design is needed |

## Results (from `sample_output.txt`, seed 42)
| | Safe design | Naive (read-then-write) |
|---|---|---|
| Units sold | **100** | **650 (oversold by 550)** |
| Requests reaching DB | 107 of 10,200 | all |
| Answered at L1 CDN / L2 local / L3 pool / replay | 9,921 / 163 / 7 / 2 | – |
| Duplicates collapsed | 200 / 200 | – |
| Failed payments → resold | 7 → 6 resold | – |
| Events outboxed during Order outage → orders created after outage | 100 → 100 | – |
| Max charges per customer | 1 | – |
| Invariant checks / violations | 415 / **0 – PASS** | **FAIL** |

Limitations: a threaded in-memory model, not a real Redis/Postgres; tier hit counts depend on the simulated timing. It validates the *logic* of the design, not production throughput.
