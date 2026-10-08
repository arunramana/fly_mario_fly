# RESULTS: which wiring feature carries the E1 jump advantage (2026-10-07)

Pre-registered in docs/SPEC_e1_features.md before any episode of the new arms ran (P counts, arms, readings, status rule, CI methods,
re-analysis plan). Seeds 3700-3749, gate on, real network hash 3848f3e70b2051ef. Existing real and class arms were NOT re-run
(audit/p23_e1_n50.json); `path_kept` and `path_shuffled` were run once each, 50 episodes, 8 workers, `audit/p24_run.py` (the p23 pattern:
same jobs as `brain.e1.run_eval`, same `run_e1_episode`, same WorkerPool, `record_rows=True`; raw `audit/p24_e1_paths.json`). Analysis:
`audit/p24_stats.py` -> `audit/p24_stats.json`. Rewiring hashes: `audit/p24_hash.py` -> `audit/p24_hash.json`.

## 1. Re-analysis with the trajectory as the unit (existing data, no new runs): real vs class
Trajectory = tuple of SPEC_e1_n50 section 3. No trajectory carried both outcomes in either arm.

| quantity | real | class |
|---|---|---|
| episodes | 50 | 50 |
| distinct trajectories (units) | 16 | 38 |
| Kish n_eff | 7.1 | 26.6 |
| surviving trajectories | 14/16 (0.875) | 29/38 (0.763) |
| multiplicities (largest) | 15,6,5,5,4,3,3, then 1 x 9 | 5,4,3,2,2,2, then 1s |

| test | value |
|---|---|
| naive episode-level Fisher (SPEC_e1_n50) | p = 0.00064; diff +0.30; Newcombe 95% CI +0.137 to +0.447 |
| trajectory-level permutation (100,000, seed 20261007), stat = surviving-trajectory proportion real - class = +0.112 | **two-sided p = 0.475** |
| cluster bootstrap (10,000, seed 20261007), episode-level survival diff, percentile 95% CI | +0.019 to +0.516 (point +0.30) |
| cluster bootstrap, trajectory-weighted statistic | -0.102 to +0.316 |
| pre-registered robustness rule (permutation p < 0.05 AND bootstrap CI excludes 0) | **not met** |

Verdict, per the SPEC rule: the n = 50 result is NOT robust to non-independence at the trajectory level. Effective sample size is
about 7 (real) and 27 (class), not 50. The 46/50 vs 31/50 gap survives only as an episode-weighted statement: the episode-weighted
bootstrap interval barely excludes 0 (lower end +0.019), the trajectory-level permutation test gives p = 0.47, and the trajectory-weighted
interval includes 0. The real arm's 4 deaths fall in 2 trajectories (multiplicities 3 and 1), the class arm's 19 deaths in 9 trajectories, so at
trajectory level the failure rate is 2/16 vs 9/38, a difference too small to separate at these unit counts.

## 2. The control arms (seeds 3700-3749, paired with the existing arms)
Distinct rewirings: path_kept 50 of 50 distinct hashes, path_shuffled 50 of 50 distinct hashes, none equal to the real hash, no hash
shared between the two arms (shuffle seeds 1..50; audit/p24_hash.json).

| quantity | real | class | path_kept | path_shuffled |
|---|---|---|---|---|
| survived | 46/50 | 31/50 | **4/50** | **4/50** |
| Wilson 95% CI | 81.2-96.8% | 48.2-74.1% | 3.2-18.8% | 3.2-18.8% |
| Fisher p vs real (two-sided) | - | 0.00064 | 1.1e-18 | 1.1e-18 |
| Fisher p vs class | 0.00064 | - | 1.3e-08 | 1.3e-08 |
| D vs real (Newcombe 95% CI) | - | -0.30 (-0.447, -0.137) | -0.84 (-0.909, -0.687) | -0.84 (-0.909, -0.687) |
| D vs class (Newcombe 95% CI) | +0.30 | - | -0.54 (-0.671, -0.364) | -0.54 (-0.671, -0.364) |
| outcomes | stomped 46, died 4 | stomped 26, passed 5, died 19 | stomped 4, died 46 | stomped 4, died 46 |
| distinct trajectories (of 50) | 16 | 38 | 38 | 38 |
| GF fired (of 50) | 50 | 50 | **0** | **0** |
| A-run bins 1 / 2 / 3-5 / 6-10 / 11+ | 3/0/8/88/0 | 6/8/29/26/27 | 4/7/6/0/0 | 4/7/6/0/0 |
| A runs total; episodes with no A press | 99; 0 | 96; 0 | 17; 43 | 17; 43 |
| GF spike-to-contact lead (frames) | median 27 (26-27; 15-29) | 21 (18-24; 14-34) | no GF spike, undefined | undefined |
| fraction of advantage retained f | 1 | 0 | -1.8 | -1.8 |

Pre-registered status rule, applied mechanically: path_kept: CI(D_real) excludes 0, CI(D_class) excludes 0 -> **N**. path_shuffled: same -> **N**.
Both point estimates are outside [class, real] (worse than class, 4 < 31) -> the SPEC's own case "N with a point estimate outside
[class, real] (better than real or worse than class) -> **anomalous**, reported as is, no reading."

**Pre-registered reading: anomalous. No location (local / outside / distributed) is claimed.** The four-way pre-registered sentence
("path-kept ~ real AND path-shuffled ~ class -> local ... ") is not satisfied: path_kept is not ~ real (D = -0.84), path_shuffled is not
~ class (D = -0.54).

### Surprising, stated plainly
- Both control arms are worse than the full class shuffle and indistinguishable from a degree shuffle: the Giant Fiber never fired in
  any of 100 episodes (0/100; class 50/50, real 50/50). With the GF silent, Mario dies at the Goomba in 46/50.
- The two arms are identical episode by episode: for all 50 seeds the outcome, frame count and full A trace of path_kept equal those of
  path_shuffled (50/50 identical), even though the networks are different (100 distinct hashes, none equal to the real hash, no hash shared
  between arms). Interpretation offered only as a hypothesis, not tested: with the GF silent the trajectory is determined by the noise seed
  and the policy, not by the (irrelevant to behaviour) rewiring. This is also why both arms have 38 distinct trajectories (as many as the
  class arm, whose trajectories do vary by rewiring); the 38 here come from the noise seed. I did not run a second implementation of the arm,
  so a defect in the arm wiring is not excluded by this sprint; the hashes are distinct, which says only that the post columns differ.
- Why shuffling EITHER the 13,291 P-P edges OR the other ~624,000 edges silences the GF while shuffling all edges does not is not
  explained by anything measured here. Structural diagnostic (no episodes, shuffle seed 1; audit/p24_diag.py): total input weight onto the
  two GF cells is 1.971 (real), 1.969 (class), 1.971 (path_kept), 1.968 (path_shuffled); weight from LC4/LPLC2 onto GF 0.632 in all four with
  the same 302 non-zero entries (the class machinery permutes GF-bound edges only among the GF tier group, which leaves them on the GF);
  LC4/LPLC2 lateral weight 147.9 (real), 160.3 (class), 151.2 (kept), 155.7 (shuffled). So direct LC4/LPLC2 -> GF drive is unchanged in all
  four networks; whatever silences the GF in the new arms is elsewhere (lateral/relay structure, i.e. where the dynamics are), and the
  full class shuffle does not silence it. Not pursued further (rule: measure, do not explain away).
- These two arms do not interpolate between real and class. The design assumed class lies at one end and real at the other, with
  partial shuffles between; the partial shuffles instead fall below the class end. Caveat on the constructions: `path_kept` adds ~2%
  chance P-P edges (SPEC section 2), and `path_shuffled` shuffles within P by tier group; these are constructions, not natural networks.
  "Path" is defined by the one-intermediate criterion, so conclusions about "the pathway" are conclusions about that set only.

## 3. Sensory vs motor, existing data (real vs class; Mann-Whitney U two-sided / Fisher, no multiplicity correction; descriptive, no causal claim)
Episodes are treated as independent in these p-values, which Section 1 shows is generous to the real arm (its sensory columns are
almost constant); read the effect sizes, not the p-values.

| side | quantity | real | class | p |
|---|---|---|---|---|
| sensory | GF fired | 50/50 | 50/50 | - |
| sensory | first GF frame, median (range) | 109 (109-114) | 106 (98-106) | 3.6e-21 |
| sensory | distance at first GF spike, px | 12 (9-12) | 14 (14-19) | 1.6e-21 |
| sensory | theta at first GF spike, deg | 45.2 (45.2-58.1) | 39.3 (29.5-39.3) | 1.6e-21 |
| sensory | spike-to-contact lead, frames | 27 (26-27; 15-29) | 21 (18-24; 14-34) | 1.1e-06 |
| motor | A onset after first GF spike, frames, median (IQR) | 5 (5-5) | 1 (0-3) | 6.5e-11 |
| motor | A runs per episode, median | 2 | 2 | 0.17 |
| motor | A-run length median | 7 | 6.5 | 0.60 |
| motor | share of runs 6-10 frames | 88/99 (89%) | 26/96 (27%) | 1.6e-19 |
| motor | share of taps (<= 2 frames) | 3/99 (3%) | 14/96 (15%) | 0.0048 |
| motor | share of runs 11+ frames | 0/99 | 27/96 (28%) | 5.6e-10 |
| motor | episodes where every A run is 6-10 frames | 42/50 | 5/50 | - |

Context (not part of the classification): path_kept and path_shuffled have no sensory side (GF never fired, lead and onset undefined) and
a motor side of 17 runs in 7 of 50 episodes (43 episodes press no A at all), 11 of the 17 being taps.

Verdict: both sides differ. Sensory differences are small in absolute terms (class GF fires 3 frames earlier, 2 px farther out, at 6
deg smaller theta; lead 6 frames shorter). Motor differences are large (A starts 5 frames after the spike in real vs 1 in class; 89% of
real runs are 6-10 frame holds vs 27%; class has 28% of runs 11+ frames and 15% taps). The number of A runs per episode and the median run length
do not differ. The larger contrast is on the motor side (hold shape and onset delay), but the spike-to-contact lead depends on Mario's
motion after the press and is not a pure sensory measurement; no claim is made that either side causes the survival gap.

## Sprint-boundary tests
Affected tests (tests/test_e1_features.py, test_workers.py, test_e1.py): 26 passed. Root `tests`: 338 collected (unique), 3 disjoint
chunks of 47 files, 3 processes: 91 + 123 + 124 = 338 passed, 0 failed. `pytest -m fast tests`: 13 passed, 325 deselected. Logs:
audit/p24_pytest_aff.log, audit/p24_pytest{0,1,2}.log. No repo code, config or tests were edited.

---
VOID NOTE (2026-10-08, appended, nothing above rewritten): the path_kept and path_shuffled results in section 2 (4/50 and 4/50, GF silent in 100/100,
status N/N, reading "anomalous", the "worse than the class shuffle" and "identical episode by episode" statements) are VOID. Cause: brain/e1.py
`run_e1_episode` passed shuffle_mode "degree" to the policy for the path arms, so both ran plain degree-shuffled networks. Fixed in brain/e1.py;
corrected re-run in docs/RESULTS_e1_followup.md (path_kept 33/50, path_shuffled 42/50; mechanical reading "lies outside the pathway", not
supported at the trajectory level). Sections 1 (real vs class re-analysis) and 3 (sensory vs motor) do not use those arms and are unaffected.
