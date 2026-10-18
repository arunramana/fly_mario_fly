# S3: rim tiles + pit hole + robustness + controls

Spec file `claude/flyrun-behaviour-spec.md` is not in the repo; built from the S3 message. Senses v2 + motor v2, default knobs, no tuning, no search, no new knobs.
**Result: the S2c win does not survive 0b. The real fly is 0/10 on HOLDOUT; he dies in pit 1 (x ~1128) in 9 of 10 episodes. No rule was changed.**

## 0a. Rim tiles
Surveyed every 1-1 pipe column with the scripted driver (tile column, rows 7-12): pipes 1-3 have rim ids 18/19, **pipe 4 has 16/17** (the only 16/17 in the level);
bodies are 20/21 everywhere. `level.RIM_TILES = {16, 17}`; `scan_visible(ram, rim=True)` counts them as wall. Deviation from "add to SOLID_WALL": senses v2 passes rim=True,
v1 does not, so every Part 1-7 result still reproduces (the v1 reproduction test passes). Pipe 4 now reads 64 px. Test: `test_rim_tiles_16_17_make_pipe_4_read_64px_in_v2_only`.

## 0b. Pit = the hole
Removed the 68 px virtual wall and the pit-below rule. A pit is ONE threat: the rectangle x in [near edge, far edge], y in [floor, floor + 16] (floor = y 176).
**Eye point (defined once, `senses_v2.hole_theta`): the top-front corner of MARIO_BOX = (mx + 12, feet - 16).** theta = the angle that rectangle covers from the eye
(the arc left after removing the largest gap between the four corner directions; eye inside the rectangle -> pi). d = the 2-D box gap, as for every object.
Threat ends once his left edge is at/past the far edge. Enemies and faces unchanged.
- **Trigger angle of the real fly: 43.6 deg** = median theta at his 50 grounded A onsets on enemies / faces over the HOLDOUT runs (range 41.1-50.4; `runs/S3_holdout.json`).
- On foot, a 32 px pit: theta first reaches 43.6 deg at **17 px** from his front edge to the near edge (24 px: 37 deg). Within 24: yes.
- **Airborne over the gap: theta does NOT stay above the trigger.** With the eye at the top-front corner and the hole below, theta is ~23 deg all the way over a 32 px gap
  when he is ~60 px up (test `test_airborne_over_the_gap_theta_stays_above...` is an expected failure, `xfail(strict)`). The pit is still the chosen threat on every frame until he is past the far edge, and gone after (tests pass).
- Why this matters: pit 1 jump in the smoke run (frames 674-700): take-off 15 px before the edge at theta 43.9 deg, A held 6 frames, theta falls as the eye rises (46 -> 38 deg), TTMn 0.109 -> 0.096 < 0.10, A released at frame 680
  with the feet only 23 px up; apex feet y 135 (41 px up); he falls into the hole. theta and TTMn rise again on the way down (64 deg) but A cannot be pressed in the air.
- Tests changed: pit tiles/virtual wall tests replaced by hole tests; 3 S2c wall tests removed; the kinds set loses "pitwall". Added: hole theta geometry, on-foot crossing (17 px), rim. flyrun suite: see commit.

Smoke (noop 0, sigma 0, unassisted; `runs/S3_smoke_log.csv`, `S3_jumps.csv`): **no flag**, max_x 1128, died in pit 1. Pipes 1-3 in one jump each; pipe 4 (now 64) needs 2 jumps (first lands at its foot, x 899); pit 1 crossed in 0 of 1 jumps (take-off 15 px from the edge). Pit 2 never reached.

## 1. Robustness: real wiring, Part 6b HOLDOUT (10 episodes)
| noop | seed | sigma | flag | max_x | end (x, cause) | blind | Left presses | A frac |
|---|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | no | 1128 | died (1128, pit) | 2 | 0 | 0.23 |
| 11 | 102 | 0.0 | no | 1128 | died (1128, pit) | 2 | 0 | 0.23 |
| 25 | 103 | 0.0 | no | 1128 | died (1128, pit) | 2 | 0 | 0.23 |
| 33 | 104 | 0.0 | no | 1128 | died (1128, pit) | 2 | 0 | 0.23 |
| 41 | 105 | 0.0 | no | 1128 | died (1128, pit) | 2 | 0 | 0.22 |
| 3 | 101 | 0.05 | no | 1128 | died (1128, pit) | 2 | 0 | 0.24 |
| 11 | 102 | 0.05 | no | 1414 | died (1414, pit) | 3 | 0 | 0.21 |
| 25 | 103 | 0.05 | no | 1127 | died (1127, pit) | 2 | 0 | 0.23 |
| 33 | 104 | 0.05 | no | 1128 | died (1128, pit) | 2 | 0 | 0.23 |
| 41 | 105 | 0.05 | no | 1127 | died (1127, pit) | 2 | 0 | 0.22 |

Flag rate **0/10**. Distinct trajectories: 10 by full (x, A) trace (they differ by start timing / noise), but **3 by (max_x, death x)**: 1128 (7 episodes), 1127 (2), 1414 (1). Nine of ten die at pit 1 (x 1127-1128, cause pit); one (noop 11, sigma 0.05) crosses pit 1 and dies in pit 2 at x 1414. Left presses 0 everywhere, blind presses 2-3 (limit 8).

## 2. Controls (same 10 episodes, same senses + motor + knobs; only the brain differs)
| arm | flags | mean max_x | min max_x | distinct (max_x, end x) | distinct traces | blind presses (total) | Left presses | silence A_frac |
|---|---|---|---|---|---|---|---|---|
| real | 0/10 | 1156 | 1127 | 3 | 10 | 21 | 0 | 0.00 |
| shuf0 | 0/10 | 40 | 40 | 1 | 5 | 0 | 10 | 0.00 |
| shuf1 | 0/10 | 40 | 40 | 1 | 5 | 0 | 10 | 0.00 |
| shuf2 | 0/10 | 40 | 40 | 1 | 5 | 0 | 10 | 0.00 |
| shuf3 | 0/10 | 40 | 40 | 1 | 5 | 0 | 10 | 0.00 |
| shuf4 | 8/10 | 2588 | 298 | 2 | 5 | 174 | 0 | 0.96 |
| theta_rule | 0/10 | 1155 | 1125 | 3 | 10 | 21 | 0 | 0.00 |
| blind_timer | 0/10 | 298 | 298 | 1 | 5 | 40 | 0 | 0.75 |

theta-rule trigger = 43.6 deg (the real fly's measured median); blind timer = Right always, A held 30 of every 40 frames. Silence = 600 frames with no enemies, pipes or pits in view.
- shuf0-3 never walk: they press Left on the first frames and stay at x 40 ("stuck"). Their distinct-trace count only reflects start timing. The test is therefore weak for them.
- **shuf4 flags 8/10 but fails the silence test: A is down 96% of the time with nothing in view** (TTMn sits above threshold at rest), i.e. a held-down A with landing resets. It is a button-mash that happens to clear this level (174 blind presses, 2 deaths at x 298 to the first Goomba). Its flags are disqualified by the standing silence constraint; they are not evidence for or against the wiring.
- theta-rule dies in pit 1 at x 1125-1126 in 9 of 10 episodes (one reaches pit 2, 1422): the same failure as the real fly.
- blind timer: 0/10, dies to the first Goomba at x 298 every time.

## Paragraph
(a) **Robustness:** there is no robust win to measure. With the true-angle pit hole the real fly is 0/10 on HOLDOUT and 9/10 die at the same place, pit 1, for the same mechanical reason: the hole's angle shrinks as his eye rises, TTMn falls under threshold 6 frames into the jump, A is released and cannot be re-pressed in the air, so the hop is too short. The earlier flag (S2c, 3161, one episode) used the 68 px virtual wall, which is removed.
(b) **Wiring vs controls:** on this HOLDOUT the real wiring does nothing the theta-rule does not: both reach the same death, at nearly the same x (1128 vs 1126; 1156 vs 1155 mean). Four of five shuffles cannot walk at all; the fifth clears the level only by holding A all the time and is disqualified by silence. The real fly passes the silence test, walks, and jumps to obstacles, and so does the theta-rule; nothing in this data separates them. Not shown: that the connectome matters for this behaviour. Not tested: what happens with a different eye point or pit geometry (not done, by instruction).

Files: `s3_eval.py`, `s3_controls.py`, `smoke_s3.py`, `runs/S3_holdout.json`, `runs/S3_smoke_log.csv`, `runs/S3_jumps.csv`; clips (gitignored) `clips/S3_real_run.mp4` (the real fly, noop 0 sigma 0, 1x, 11.9 s - named `_real_run` rather than `_win` because it is not a win), `clips/S3_death_pit1.mp4` (2.8 s, 0.5x, HOLDOUT episode noop 3 seed 101).
