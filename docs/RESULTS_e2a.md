# RESULTS: E2a (obstacle expansion, pipe 1) and the 1-1 baseline re-run with obstacle expansion

Experimenter run, 2026-10-05. Network 3848f3e70b2051ef, calibration 343d8f60abcdba25. No code, config or parameter edits; each eval run once.
Raw: audit/p7_e2a.json, audit/p7_b11.json. Criteria were stated in docs/SPEC_e2a.md before running.

## E2a (seeds 7100-7119, shuffle seed 1+i, 600 frames, obstacle expansion ON except the necessity arm)
Command: `python -m brain.e2a --n 20 --seed0 7100 --workers 4 --out audit/p7_e2a.json`

| arm | cleared (Wilson 95% CI) | ends | GF fired (before face) | GF x / d / theta at 1st spike (median) | first A frame / x (median) | first-A run | take-off x | tap frac | GF max Hz | TTMn max Hz |
|---|---|---|---|---|---|---|---|---|---|---|
| real | 18/20 (70-97%) | cleared 18, stuck 2 | 20 (20) | x 417.5 / 30.5 px / 41.8 deg | 52 / x 431 | 12 of 1 frame, 8 of 9-13 | 434 | 0.60 (12/20) | 12.0 | 0.327 |
| shuffled (degree) | 0/20 (0-16%) | timeout 20 | 20 (20, trivial) | x 321 / 127 px / 13.5 deg | 1 / x 321 (13/20 pressed) | 4-24 | 321 | 0.0 | 12.0 | 0.780 |
| shuffled_class | 0/20 (0-16%) | timeout 20 | 0 (0) | none | 2 / x 321 (1/20 pressed) | 5 | 321 | 0.0 | 0.0 | 0.101 |
| real_no_obstacle | 0/20 (0-16%) | stuck 20 | 0 (0) | none | none (no A) | none | none | none | 0.0 | 0.013 |

| criterion | threshold | observed | result |
|---|---|---|---|
| real clears pipe 1 | >= 14/20 | 18/20 | PASS |
| degree shuffle | <= 2/20 | 0/20 | PASS |
| real_no_obstacle | <= 2/20 (expected) | 0/20 | PASS |
| class shuffle | informative only | 0/20 | n/a |

Notes (plain):
- Real is not a single trajectory: first GF spike at x 413-422 (4 values), first-A x 422-434, first-A run 1 frame (12 episodes) or 9-13 frames (8). The 2 failures (seeds 7109, 7110) are 1-frame taps at x 434 (the stall point), max_x 436: too late for a 1-frame hop (window 5-29 px before 434). Of the 12 tap episodes 10 cleared; all 8 long-hold episodes cleared. Correlation, not a paired test.
- Shuffled arms: Mario never moves from the scene start (max_x 321 in all 20, timeout). The degree shuffle's GF fires on the first frame (d 127 px, theta 13.5 deg, i.e. not obstacle-driven): these shuffles are broken in a way unrelated to the pipe (no walking drive at all; A pressed at frame 1). Their 0/20 therefore says the real circuit walks and the shuffles do not, not that the shuffles fail the pipe specifically. The same held in baseline B11 (shuffles stuck at left edge).
- The real GF threshold crossing is 29-30 px before the face, theta about 42 deg, consistent with INVESTIGATION_phase6 (b) (about 40 px) and the synthetic disc range.
- Scene disclosure: first Goomba removed (clear_enemies), home landmark on.

## 1-1 innate baseline B11, WITH obstacle expansion (seeds 6100-6119, 3000 frames, stuck 300)
Command: `python -m brain.baseline --n 20 --seed0 6100 --workers 4 --out audit/p7_b11.json`. Baseline, no pass/fail.

| arm | max_x mean (bootstrap 95% CI) | median / min / max | ends | Goombas jumped / encountered | pipe 1 cleared | A-tap episodes | A runs 1 / 2 / 3-5 / 6-10 / 11+ | power-up | GF fired / GF max Hz / TTMn max Hz |
|---|---|---|---|---|---|---|---|---|---|
| real | 417 (356-499) | 315 / 315 / 724 | died_enemy 15 (all x 315, frame 106), stuck 5 (x 722, 723, 724, 724, 724; frames 562-796) | 10 / 25 (5 episodes) | 5/20 | 0/20 | 11 / 0 / 15 / 12 / 14 (52 runs) | 0 released, 0 collected | 20 / 12.0 / 0.349 |
| shuffled (degree) | 40 (40-40) | 40 / 40 / 40 | stuck 20 | 0 / 0 | 0 | 0/13 | 0 / 0 / 2 / 2 / 9 | 0 / 0 | 20 / 12.0 / 0.776 |
| shuffled_class | 40 (40-40) | 40 / 40 / 40 | stuck 20 | 0 / 0 | 0 | 0/1 | 0 / 0 / 1 / 0 / 0 | 0 / 0 | 0 / 0.0 / 0.101 |

Pipe-1 cleared is read from max_x > 479 (the 5 survivors reach x 722-724, the next obstacle, and stall there).

| baseline | real max_x mean | died at first Goomba | stalled | where stalled | level complete |
|---|---|---|---|---|---|
| WITHOUT obstacle expansion (seeds 6000-6019, earlier run, not edited) | 357 | 13 | 7 | pipe 1, x 434 | 0/20 |
| WITH obstacle expansion (seeds 6100-6119, this run) | 417 | 15 | 5 | x 722-724 (beyond pipe 1) | 0/20 |

Notes (plain):
- Obstacle expansion carries every Goomba survivor past pipe 1 (5/5; before, 0/7). It does not help the Goomba: 15/20 die at frame 106, x 315 (earlier 13/20). Different seeds, so 13 vs 15 is not evidence of an effect; both are the same two-trajectory baseline.
- All survivors then stall at x 722-724 (all 5 within 3 px) and stay stuck 300 frames; no episode reaches the mushroom or the flag. The stall is not characterised here (not diagnosed).
- Note the baseline is effectively two trajectories (die at 315 or pass to ~724), so n=20 carries little independent information.
- Shuffles: max_x 40 everywhere, as before.

## Videos (seed 9200) and tests
projects/redesign_e1/runs/223a_e2a_real_seed9200.mp4 (cleared, 86 frames), 223b_e2a_real_no_obstacle_seed9200.mp4 (stuck at x 436), 224a_b11_real_seed9200.mp4 (died_enemy frame 106, x 315). The Experiments launcher cannot select the real_no_obstacle arm (run_brain_one maps shuffle_seed None to "real"), so 223b was produced by calling run_e2a_episode directly (audit/p7_video2.py).
Root tests/ (all 42 test files, run in 3 chunks, goldens included): 288 passed, 0 failed (101 + 94 + 93).

## Synthetic validation (implementer, before any game run; `audit/e2a_synth.py`, open loop, face at x 448, stall x 434, start d 130)
Speeds measured on the emulator: walking 1.75 px/frame, running 3 px/frame. Real: 3 noise seeds; shuffles: 5 degree shuffles. Nothing tuned.
- **Pipe 1 (32 wide), theta by distance:** d<=128 13.5 deg, d<=64 24.7, d<=40 35.4, d<=24 48.1, peak 50.2.
- **Real arm:** GF fires 3/3 at d about 31 px (41.5 deg), 17 px before the stall point. First A press 5.3 px before the stall point running (range 0-8), 12.8 px walking (11-14.5). About 100-126 GF spikes in 160 frames.
- **Timing slack vs INVESTIGATION_phase6 take-off windows:** a 1-frame tap clears only if pressed 5-29 px before the stall point, so the running press (0-8) sits at or below the lower edge (borderline); walking (11-14.5) is inside. The A press is a sustained run in the bench (about 17 frames), and holds of 3+ need 0-41 px, 8+ need 0-65: inside those windows.
- **Block (16 px) and first stair step:** late. GF at d about 19 px (45.7 deg), only 5 px before the stall point; first A 2-5 px before it (walking 0.5-5.8). No clearance window was measured for these, so no clearance claim.
- **Shuffles:** landmark off, GF 0/5 and no A for every geometry and speed. Landmark on, every shuffle saturates the GF from frame 0 (d about 129), so only the landmark-off comparison is informative.
- **Flat ground:** theta exactly 0 on every frame of a 3000 px synthetic walk; in the emulator the first obstacle ever seen is pipe 1 (drawn once x >= 304).
- **Disc with ObstacleExpansion attached and landmark on:** GF first spike 47.2 (l/v 10), 47.2 (20), 40.6-47.2 (40), 43.6 (80) deg. Rest, 1000 frames: 0 GF spikes (real, landmark off and on; shuffles 1-3 landmark off).
- **Elevation weighting, plain:** the obstacle theta is multiplied by the same elevation weight as enemies, using the face centre (pipe 1 centre is 8 px above Mario's). This lowers theta below the unweighted value (35 deg instead of 43.6 at d=40), so the GF fires closer to the face than the unweighted investigation figure; the real-arm theta at the GF spike is about 42 deg.

## Caveats on the cue
- "Solid" = any non-zero tile in the block buffer. Verified only on the first 900 frames of 1-1 (pipes 0x12-0x15, brick 0x51, ground 0x54, "?" 0xC0/0xC1). Hidden blocks, coins and other levels are unchecked; a hidden block could read as a drawn obstacle.
- The B11 stall at x about 724 (undiagnosed) could be this cue acting on that obstacle, or an unrelated obstacle; this document does not tell them apart.
