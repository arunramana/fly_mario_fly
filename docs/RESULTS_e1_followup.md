# RESULTS: E1 follow-up, corrected path arms and E1d scene distribution (2026-10-08)

Measurement only: no repo code, config or tests were edited by the experimenter. Each run was done once.

## 0. The defect, and what is void
`brain/e1.py` `run_e1_episode` passed `shuffle_mode="degree"` to the policy for every shuffled arm, so `path_kept` and `path_shuffled`
(RESULTS_e1_features.md section 2, RUNS 234) ran plain degree-shuffled networks: the Giant Fiber was silent in all 100 episodes and the two arms
were identical episode by episode. The coordinator fixed it (`ARM_SHUFFLE_MODE.get(arm, "degree")`). **Every path_kept / path_shuffled number from
the 3700-3749 run (audit/p24_e1_paths.json: 4/50 and 4/50, status N/N, reading "anomalous", the "worse than the class shuffle" statement) is VOID.**
The real, class and trajectory-clustering results of RESULTS_e1_features.md section 1 and the sensory/motor section 3 do not involve those arms and stand.
Tests: `tests/test_e1_features.py` + `tests/test_e1.py` 28 passed, including the 2 previously failing
`test_each_arm_hands_its_own_shuffle_mode_to_the_policy[...]`.

## 1. Path arms re-run (seeds 3700-3749, paired with the existing real and class arms, not re-run)
Script audit/p25_run.py (p24 pattern, record_rows=True, WorkerPool 8, worker-side network hash recorded) -> audit/p25_e1_paths.json;
stats audit/p25_stats.py -> audit/p25_stats.json; trajectory-level tests audit/p25_traj.py -> audit/p25_traj.json; hashes audit/p25_hash.py.

Sanity: worker-side hashes 50 distinct of 50 per arm; none equal to the real hash or to any of the 50 degree-shuffle hashes; the two arms share
no hash; GF fired 50/50 in both arms (was 0/100); identical episodes between the arms 0/50 (was 50/50).

| arm | survived | Wilson 95% | Fisher p vs real | vs class | D vs real (Newcombe 95%) | D vs class (Newcombe 95%) | status |
|---|---|---|---|---|---|---|---|
| real (existing) | 46/50 | 81-97% | | 0.00064 | | | |
| class (existing) | 31/50 | 48-74% | 0.00064 | | | | |
| path_kept | 33/50 | 52-78% | 0.0026 | 0.835 | -0.26 (-0.41 to -0.10) | +0.04 (-0.14 to +0.22) | C |
| path_shuffled | 42/50 | 71-92% | 0.357 | 0.023 | -0.08 (-0.21 to +0.05) | +0.22 (+0.046 to +0.378) | R |

| arm | outcomes | distinct trajectories | A runs 1 / 2 / 3-5 / 6-10 / 11+ | GF-to-contact lead (median, IQR) | A onset after GF (median) |
|---|---|---|---|---|---|
| real | stomped 46, died 4 | 16 | 3 / 0 / 8 / 88 / 0 | 27 (26-27) | 5 |
| class | stomped 26, died 19, passed 5 | 38 | 6 / 8 / 29 / 26 / 27 | 21 (18-24) | 1 |
| path_kept | stomped 30, died 17, passed 3 | 32 | 6 / 10 / 36 / 34 / 8 | 24 (21-28) | 5 |
| path_shuffled | stomped 41, died 8, passed 1 | 45 | 2 / 7 / 10 / 44 / 37 | 24 (21-27) | 0 |

Pre-registered rule applied mechanically (SPEC_e1_features.md section 4): (path_kept, path_shuffled) = (C, R) -> **"lies outside the pathway"**.
Fraction of the advantage retained f = (A - class)/(real - class): path_kept 0.13, path_shuffled 0.73 (point estimates, not used for the status).

Trajectory-level caveat (real has 16 distinct trajectories, Kish n_eff 7.1; episode-level p-values are generous). Trajectory units, permutation
test 100,000 / cluster bootstrap 10,000, rng seed 20261007:

| contrast | distinct traj | permutation p (trajectory) | bootstrap CI, episode-weighted | bootstrap CI, trajectory-weighted |
|---|---|---|---|---|
| path_shuffled vs class (episode Fisher 0.023) | 45 vs 38 | 0.150 | -0.042 to +0.456 | -0.038 to +0.294 |
| path_kept vs real (episode Fisher 0.0026) | 32 vs 16 | 0.295 | -0.479 to +0.006 | -0.375 to +0.063 |
| path_shuffled vs real (n.s.) | 45 vs 16 | 1.0 | -0.255 to +0.136 | -0.156 to +0.224 |
| path_kept vs class (n.s.) | 32 vs 38 | 0.785 | -0.252 to +0.320 | -0.248 to +0.164 |

Reading. The (C, R) classification rests on episode-level Newcombe intervals. Both contrasts that drive it (path_shuffled above class,
path_kept below real) fail the trajectory-level test (p = 0.15, 0.30; the bootstrap CIs include 0). The classification inherits the weakness of
the real-vs-class gap itself (trajectory permutation p = 0.475, RESULTS_e1_features.md section 1). The mechanical reading is "lies outside the
pathway"; it is not supported at the trajectory level, so no location is established.

## 2. E1d, independent scenes (docs/SPEC_e1_scene_dist.md; pre-registered; run once)
`python -m brain.e1 --scene-dist --n 50 --seed0 3800 --workers 8 --arms real shuffled_class --out audit/p25_e1d.json`; stats
`audit/e1d_stats.py` -> audit/p25_e1d_stats.json. Scene e1d_goomba_dist (2d26a3fe0d295a03), network 3848f3e70b2051ef.

| quantity | real | class |
|---|---|---|
| survived | 38/50 | 42/50 |
| Wilson 95% | 63-86% | 71-92% |
| outcomes | stomped 38, died 12 | stomped 41, died 8, passed 1 |
| distinct trajectories / Kish n_eff | 50 / 50.0 | 50 / 50.0 |
| GF fired, GF before contact | 50/50, 50/50 | 50/50, 50/50 |
| GF-to-contact lead (median) | 22 | 23 |

Fisher two-sided p = 0.454 (one-sided real > class 0.895). Difference (real - class) = -0.08, Newcombe 95% CI -0.234 to +0.078.
Trajectory-level permutation p = 0.455; cluster-bootstrap CI of the difference -0.24 to +0.08 (episode- and trajectory-weighted identical, since
every episode is its own trajectory). Distinct scenes drawn: 47 of 50 (expected 47.6). Paired: both survived 32, real only 6, class only 10.
Class numerically beat real; the pre-registered sentence is not applied for that direction.

Pre-registered reading (literal: "p < 0.05 AND the CI of the difference excluding 0 at the trajectory level -> fine wiring matters for the
jump in this scene distribution; otherwise not shown (unresolved)"): p = 0.454 is not < 0.05 and the CI includes 0 -> **not shown (unresolved)**.
The script's stricter rule (also requires real > class) gives the same verdict, "not shown (unresolved)". Both agree.

## 3. What these two experiments leave
Under independent scenes the real and class networks are indistinguishable on the jump (38 vs 42 of 50). The fixed-scene advantage (46 vs 31) is
therefore not shown to be a property of the wiring across scenes; with a single scene it is a property of 16 trajectories. The corrected path
arms sit between class and real only at the episode level and not at the trajectory level.

## Sprint-boundary tests
Affected (tests/test_e1_features.py + tests/test_e1.py): 28 passed. `pytest -m fast tests`: 13 passed, 336 deselected. Root `tests`: 349 collected (unique), 3 disjoint chunks of 16 files, 3 processes: 117 + 116 + 116 = 349 passed, 0 failed (one chunk took 61 min). Logs audit/p25_pytest{0,1,2}.log. No repo code, config or tests were edited.
