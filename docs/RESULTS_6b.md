# Phase 6b validation (2026-10-07)

Measure only: no repo code or config was edited. Scratch scripts: audit/p20_selfexc.py, p20_rest.py, p20_all.sh, p20_video.py. Raw: audit/p20_selfexc.json, p20_rest.txt, p20_{e0,e1,e2a,b11}.json, p20_pytest*.log.

## Part 1. Premise check
The requested guard `d - mario_width <= 0` was not applied. `d_surface` (brain/obstacles.py `theta_of`) already subtracts the hitbox front edge (13 small / 14 big) from `Face.d_px`; the premise described the pre-Step-4 raw `d_px`. `nearest_face` was fixed (Step 6): it picks the nearest face that can emit a cue (surface d > 0). See docs/SPEC_geometry_5c.md Step 6.

## Part 2. GF self-excitation hypothesis (pre-registered): DEAD
Parameters (brain/calibration.py): spike_amp_hz 60.0, refractory_steps 3, substeps 10, gf_threshold 0.1696 (membrane units). Mechanism (fly/network/integrator.py): on a threshold crossing GF h is set to 60 for that substep, else 0; membrane resets to 0.

B11 real, seeds 9300-9319 (replayed with current code, deterministic). Stalled (x unchanged >= 100 frames at 590-600 or 718-726, GF every frame in the second half): 15 of 20 (13 at x 594 pipe 2, 2 at x 722; the other 5: 3 died_pit, 2 died_enemy). Branch at stall onset + 50 frames. The replay is bit-identical to the control up to the branch (checked frame by frame on GF flag and membrane: True in 15/15 for both interventions).

| condition (n = 15 episodes) | GF-frames per 100 frames, before (onset..+50 frames: 50/50) | after (next 100) | GF membrane level (mean of per-frame max) | A frames pressed in the 100 after |
|---|---|---|---|---|
| A control (continue unchanged) | 100 | 100 (15/15 episodes every frame) | 0.00-0.003 | 0-100 (as before) |
| B clamp GF output to 0 (lesion semantics, mid-run) | 100 | 100 (15/15) | 0.000 | 0-9 |
| C spike_amp_hz = 0 at the branch | 100 | 100 (15/15) | 0.000 | 0-9 |
| C' spike_amp_hz = 0 whole run from reset | n/a | 5 GF frames in the run, died_enemy at x 315 after 106 frames, 15/15 | n/a | never reaches pipe 2 |

(GF firing is the per-frame flag "any threshold crossing in the 10 substeps", read before any clamp; per-substep crossings were not logged. Membrane is reset to 0 on a crossing, so a near-zero mean-of-max means it crosses at once each frame.)

Neither test stopped the firing: 15/15 stalled episodes keep crossing on all 100 frames with the GF output removed (B) and with the spike pulse removed (C). The hypothesis is dead; no third explanation was sought.

Stall stimulus (the requested context), from the obstacle channel logged by the policy during the stall: theta 175.2 deg (x 594) / 176.4 deg (x 722), d = 1.0 px (the d = 1 clamp, `d_surface` in (0, 1]), constant. LPLC2 rate 5.31-5.54 Hz, LC4 0.06 Hz (dtheta 0). This is NOT the 6-10 deg, d 59-94 px of the earlier latch note: those numbers came from telemetry rows that hold the Goomba slot (RUNS 227 said so). The wall is being read at the clamped ~pi reading, not at a weak stimulus.

From-rest control (committed brain, constant theta both eyes, 300 frames, 3 noise seeds each; GF-frames of 300): 0 to 30 deg: 0/0/0; 40 deg: 33/35/39; 90 deg: 300 x3; 175 deg: 300 x3 (LPLC2 5.1 Hz). So from rest a 6-10 deg input never fires GF; a 175 deg input fires it on every frame. The stalled firing is what a constant 175 deg input does from rest too, no recurrence needed to explain it. (Context only; not a new hypothesis.)

Consequence (as pre-registered): the confirm branch (spike_amp_hz doing structural damage, hold-duration option E to the top) was NOT triggered.

## Revalidation, fresh seeds, one run each, 3 workers
| experiment | real | degree shuffle | class shuffle | other |
|---|---|---|---|---|
| E0 4300-4319 | 20/20 (84-100%), 0 deaths, GF 0/20, median 135 frames | 0/20 (GF 20/20, A runs 13) | 0/20 | no_landmark 0/20 |
| E1 3500-3519 | 13/20 (43-82%), 7 deaths | 0/20 | 14/20 (48-85%) | lesion_gf 0/20 |
| E2a 7500-7519 | 20/20 (84-100%), first A x median 404, take-off 407, taps 5/20 | 0/20 | 0/20 | no_obstacle 0/20 |
| B11 6800-6819 | max_x mean 673 (CI 628-738), median 596 | 40 (stuck 20) | 40 (stuck 20) | |

B11 real: ends died_enemy 5, died_pit 1, stuck 14. Stalls: 12 at x 596 (pipe 2), 2 at x 722 (pipe 3). Deaths: enemy at x 722 (4) and 852, pit at 1129. Pipes cleared (max_x > 479 / 600 / 726): 20 / 8 / 2. Goombas jumped 30/31. Taps 0/20. A runs {1: 21, 2: 4, 3-5: 3, 6-10: 5, 11+: 76}. GF max 18 Hz, TTMn max 0.455 Hz. Previous (6700-6719): mean 672, 6 enemy deaths, pipes 20/13/0: the same mean within noise; pipe 2 clears were 13 before and 8 now, with 12 stalls at 596 instead of 7.

E1 real vs class, all independent fresh sets (successes of 20):

| seeds | real | class |
|---|---|---|
| 3200 | 16 | 16 |
| 3300 | 10 | 15 |
| 3400 | 13 | 16 |
| 3500 | 13 | 14 |
| pooled | 52/80 (65%) | 61/80 (76%) |

Fisher exact on the pooled counts: odds ratio 0.58, p = 0.165 two-sided (0.082 one-sided for real < class). Class was >= real in all four sets. Plainly: class >= real is consistent with the data; the pooled difference is not significant at n = 80 per arm, so the data do not show real beating the class shuffle, and do not show it losing either.

## Suite
Root tests/: 310 collected (disjoint chunks of 102 / 106 / 102 node ids, 3 pytest processes), 310 passed, 0 failed, 0 skipped, goldens included. tool/tests/test_brain_tool.py: 17 passed.

## Video
projects/redesign_e1/runs/230a_b11_real_seed9200.mp4: B11 real seed 9200, died_pit at x 1130 after 588 frames, 4 Goombas met and 4 jumped, 224 A frames. One seed is an observation, not a result.
