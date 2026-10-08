# RESULTS: E1 real vs class-shuffled, n = 50, expansion gate on (2026-10-07)

Design, pre-registered reading and the definition of "tight" were written before the run: docs/SPEC_e1_n50.md. Seeds 3700-3749 (fresh), arms real and shuffled_class only, 50 distinct class rewirings (shuffle seeds 1..50, 50 distinct hashes of 50), 8 workers, run once. Raw: audit/p23_e1_n50.json (per-episode rows with A trace), audit/p23_stats.json. Scripts: audit/p23_hash.py, p23_run.py, p23_stats.py. Real network hash 3848f3e70b2051ef.

Deviation from the spec command: the run used audit/p23_run.py (same jobs, same `run_e1_episode`, same WorkerPool as `python -m brain.e1`, with `record_rows=True`) because the CLI JSON has no per-frame A trace and the trajectory definition needs it. Nothing else differs.

## Pre-registered quantities
| quantity | real | class shuffle |
|---|---|---|
| survived | 46/50 (92%) | 31/50 (62%) |
| Wilson 95% CI | 81.2-96.8% | 48.2-74.1% |
| outcomes | stomped 46, died 4 | stomped 26, passed 5, died 19 |
| distinct trajectories (of 50) | 16 | 38 |

| test | value |
|---|---|
| Fisher exact, two-sided | p = 0.00064 |
| Fisher exact, one-sided (real > class) | p = 0.00032 |
| difference real - class | +0.30 |
| 95% CI of the difference (Newcombe hybrid-score) | +0.137 to +0.447 |
| "tight around zero" (within +-0.20 and containing 0)? | no (interval excludes 0; upper end 0.447) |

## Pre-registered conclusion (mechanical)
Real beats class with p < 0.05 (Fisher exact, two-sided, on survived counts): "the fine wiring matters for the jump and the type-level-wiring-suffices conclusion is overturned for this experiment." That is the result for the gated system, seeds 3700-3749, 50 distinct rewirings. It applies to this experiment only (E1, gate on).

## Context (not part of the reading)
- GF fired before the episode ended in 50/50 in both arms.
- Spike-to-contact lead (contact frame minus first GF frame): real median 27 frames (15-29); class median 21 (14-34).
- A-runs (maximal runs of consecutive A frames), all episodes: real 99 runs, bins 1:3, 2:0, 3-5:8, 6-10:88, 11+:0 (taps <= 2 frames: 3). Class 96 runs, 1:6, 2:8, 3-5:29, 6-10:26, 11+:27 (taps: 14). Real is a narrow hold-length distribution; class spreads from taps to 11+ frame holds. Deaths: real 4, class 19.
- Trajectory counts: real 16 distinct of 50 (near-deterministic, so the 50 seeds are fewer independent trajectories than 50 samples; Fisher treats them as independent, which is optimistic for the real arm); class 38 distinct of 50 (different rewiring each seed).
- Not pooled with the pre-gate sets (3200-3500: the expansion gate changed the input encoding) and not with the single gated set 3600-3619, shown only as context: real 19/20 vs class 12/20 there (Fisher p = 0.020); the n = 50 set agrees in direction (46/50 vs 31/50).

## Surprises
- Class passes 5 episodes ("passed", Mario goes by without stomping) that real never does.
- Earlier "type-level wiring suffices for the jump" came from pre-gate sets; the gated system reverses it. The gate (Step 7) is the only intended difference between those sets and this one, but the sets also differ in seeds, so this does not isolate the gate as the cause.
- The real-arm caveat above (16 distinct trajectories) is a limit on the strength of p, not a reason to ignore it: the class-arm variability alone (62%, CI 48-74%) sits below the real CI (81-97%) without overlap.

## Sprint-boundary tests (2026-10-07)
Root `tests` (3 disjoint chunks of files from `pytest tests --collect-only`, 3 processes): 328 collected, 328 passed (110 + 109 + 109), 0 failed, 0 skipped, goldens included. `pytest -m fast tests`: 13 passed, 315 deselected. tool/tests/test_brain_tool.py: 17 passed. Logs: audit/p23_pytest{0,1,2}.log, p23_fast.log, p23_tool.log.
