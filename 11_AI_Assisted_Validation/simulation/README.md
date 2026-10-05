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

Re-run on 2026-10-05 (same seed, box under different load; see `rerun_2026-10-05_output.txt`): tier split 9,142 / 929 / 10 / 10 replay, 109 reached DB, **100 sold, 419 checks, 0 violations – PASS**. The tier split moves with thread timing; the invariants don't.

## Resilience scenarios (`resilience_sim.py`, seed 42 – output in `resilience_output.txt`, also under `resilience` in `results.json`)
Run: `python3 resilience_sim.py` or `python3 simulate.py --resilience`.

| Scenario | Without control | With control |
|---|---|---|
| A. Retry storm: 60 s, 8k req/s fresh on 10k req/s capacity, 2 s blip to 1k req/s | naive (fixed 100 ms, 5 tries): 2,045,760 attempts (4.26×), goodput 16.7%, **not recovered** in remaining 48 s, last 10 s success 0% | budget 10% + full jitter + shedding: 483,560 attempts (1.01×), goodput 97.2%, 17,183 fast 503s, **recovered in first second**, last 10 s 100% |
| B. 30 s Order outage, 100 events, 113 deliveries (re-publishes + crash replay) | 13 duplicate orders; 11,411 consumer attempts with fixed 100 ms retry | inbox: 100 orders, **0 duplicates**; 837 attempts with backoff + jitter |
| C. Sweeper paused 15 s past 10 s lease (tokens 7 → 8) | Redis lock only: 5 stale writes applied, **3 new buyers lose their unit** | fencing: 5 stale writes rejected, **0** affected |
| D. Hot key: 10,000 buyers, 50 nodes, 16 salted sub-pools (threads) | 10,000 ops on one key | 100 tokens → 100 distinct buyers, 0 left; 900 Redis ops, max **57** on one key |
| E. Singleflight: 2,000 concurrent misses | 2,000 DB reads | **1** DB read |
| F. Coordinated omission: 1k req/s, 10 s, 2 s stall | closed-loop: p99 **1.0 ms** (8,001 samples) | open-loop from intended start: p90 1,002 ms, p99 **1,902 ms** (10,000 samples) |

Checks: PASS (0 duplicate orders with inbox, 0 buyers hurt with fencing, exactly 100 tokens to 100 buyers, 1 DB read with singleflight).

Limitations: a threaded in-memory model, not a real Redis/Postgres; tier hit counts depend on the simulated timing. It validates the *logic* of the design, not production throughput.
