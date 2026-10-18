# flyrun — PROGRESS (the scoreboard)

## Where we are
The best honest result is Part 4b's evolved fly: mean max_x **2487** on the 10 held-out start timings, but **0 flags**. Real-fly flags on held-out episodes so far: the Part 4 "hopper" (5 of 10: all five at σ 0, none at σ 0.05), Part 6b's r3 (1 of 10), and one 7d TRAIN genome that is infeasible (3 of 6 TRAIN). The strict Part 7 rules (silent when nothing is in view, first jump at a Goomba, ≤ 8 blind presses) pushed the best result down to **1629** (7e, 0/10 flags): Mario now clears the floating-ledge Goomba at x≈1220 but dies at x 1532 landing between two Goombas (7 of 10 episodes). Next: Arun's call on the x 1532 death — fix 1 diagnosed it as COOLDOWN_BLOCKED (a second Goomba arrives inside one jump's hold + cooldown), so no new sense was built and no search was run; options are in `runs/009_fix1.md`.

## Scoreboard (real fly first, oldest first; every number is from the cited file)

"best max_x" is what each source reports (mean over held-out episodes unless stated); the date is the commit date — Parts 1–6b went into one commit (`flyrun: parts 1–6b`, 2026-10-17), so they have no separate dates.

| # | date | what changed (plain English) | best max_x | flags | what stops him | clip |
|---|---|---|---|---|---|---|
| 1 | 2026-10-17 | Built the fly circuit + Mario walking right | 435 (`runs/000_scaffold.md`, test 3) | 0 | Pipe 1: no pipe sense, so he never jumps it | `runs/000_default.mp4` |
| 2 | 2026-10-17 | Added pipe and pit senses | 708 (`runs/001_senses.md`, hold/cooldown trials) | 0 | Pipe 3 (64 px) masks the Goomba; killed at 687 with default knobs | `runs/001_all_on.mp4` |
| 3 | 2026-10-17 | Combined stimuli, noise, baselines | 723 noise-free (`runs/002_fitness.md` §1) | 0 | Stuck at pipe 3 (x 722); with 30 % noise half die at Goomba #1 (296) | `runs/002_fly_default.mp4` |
| 4 | 2026-10-17 | CMA-ES evolved 6 knobs ("hopper") | 3161 = the flag, one noise-free episode (`runs/003_evolution.md`) | 1 episode (σ 0); later 5/5 at σ 0, 0/5 at σ 0.05 (`runs/004_robust.md` §3) | With 5 % noise: dead by x 1127–1220 | `clips/05_flag_run.mp4`, `clips/04_evolution_montage.mp4` |
| 4b | 2026-10-17 | Retrained on noisy episodes, penalty for blind presses | 2487 mean, 2754 at σ 0 (`runs/004_robust.md` §3) | 0/10 | Goomba at x 2754 (8/10), pit 2 (2/10) | `clips/03_theta_rule_vs_fly.mp4`, `evo4/fly/best.mp4` |
| 5 | 2026-10-17 | Added shuffled-wiring control + pit-cue ablation | 2487 (same 4b fly, `runs/005_controls.md` §1) | 0/10 | Same as 4b; the first shuffle was unfair (audit 006) | `clips/06_shuffle_SUPERSEDED_best_of_40_part5.mp4` |
| 6b | 2026-10-17 | Fair shuffle (audit fixes), equal evolution budgets | 1172 mean, best of 3 restarts (1172 / 1937 / 1405) (`runs/007_fixes.md`) | 0/10 | Goomba; r3 (1405) is later found stuck at the x≈1220 ledge | `clips/06_shuffle.mp4` |
| 7a | 2026-10-17 | Pre-registered the win search (no search run) | 1405.1 (r3 replay, `runs/008_check.md`) | 1/10 | Nothing new; HOLDOUT list fixed | — |
| 7b | 2026-10-17 | Diagnosed the x≈1220 death (no change) | 1405.1 (`runs/008b_diagnosis.md`) | 1/10 | A floating brick/?-block row the fly cannot see, Goomba on top (class OTHER); 8 of 9 deaths one trajectory | `clips/08b_death_1219.mp4`, `clips/08b_flag_same_spot.mp4` |
| 7d | 2026-10-17 | Short TRAIN search from r3 and a fresh start | 1798 TRAIN mean (`runs/008d_short_search.md`) | 0/6 TRAIN (one infeasible genome: 3/6) | Warm: Goombas 1805–2015, pit 1409; ledge cleared. Fresh 97: still at the ledge | `evo7d/warm_r3/montage.mp4` (gitignored) |
| 7e | 2026-10-17 | Full search; one HOLDOUT run of the chosen genome | 1628.8 HOLDOUT mean (`runs/008e_full_search.md`) | **0/10** | Lands between two Goombas at x 1532 (7/10), x≈2015 (2/10) | `clips/P_current_death.mp4`, `evo7e/<restart>/montage.mp4` |
| Fix 1 | 2026-10-17 | Diagnosed the x 1532 death; no sense built | 1628.8 (unchanged, `runs/009_fix1.md`) | 0/10 | One jump's 20+9 frame hold-and-cooldown can't answer a second Goomba 23 px behind the first; killed by the one ahead (class COOLDOWN_BLOCKED, stopped for Arun's call) | `clips/F1_result.mp4` |
| S1 | 2026-10-17 | Senses v2 (next threat, 2-D, sizes, faces above feet, pit tiles) | 723 smoke run, default knobs, old motor (`runs/S1_senses_v2.md`) | — | Clip shows the eye locking onto Goomba #1, pipe faces, then pipe 3 (stuck at x 722); θ saturates at ~170° when a face touches him | `clips/S1_senses_v2.mp4` |
| S2 | 2026-10-17 | Fly-held jump (press + hold by TTMn, release on fade, no cooldown) | 1127 smoke run, default knobs, senses v2 (`runs/S2_fly_held_jump.md`) | — | Pit 1: the pit's loom fades while he is over it, A is released after 7 frames, he falls in (pipes cleared on the second try) | `clips/S2_fly_held_jump.mp4` |
| S2b | 2026-10-17 | Face rule (full height from take-off ground) + pit tile under his feet | 899 smoke run (1127 in the assisted pit run), default knobs (`runs/S2b_fixes.md`) | — | Pipe 4 (48 px): A is released when his feet pass the top, he never gets over; pit 1 (assisted): loom fades during the rise, A released 5 frames before the pit-under-him threat starts | `clips/S2b_fixes.mp4` |
| S2c: face above-and-over + pit virtual wall | 2026-10-18 | Face keeps full height until feet above top AND body over it; each pit = ONE virtual wall (68 px) + tile-under-him rule; MAX_JUMP_HEIGHT 68 measured | 3161, reaches the flag (unassisted smoke run, noop 0 / seed 0 / sigma 0, default knobs, NOT a HOLDOUT result; `runs/S2c_pit_wall.md`) | 1 (smoke episode only) | Nothing stops this episode; 4 blind presses (limit 8). Level reader reads pipe 4 as 48 px, it is 64 (rim tiles 16/17 not in SOLID_WALL) | `clips/S2c.mp4` |
| S3 (0a+0b): rim tiles + pit hole | 2026-10-18 | Pipe 4 rim ids 16/17 counted as wall (v2 only; pipe 4 reads 64 px). Pit = the hole, true angle from the eye (top-front of MARIO_BOX); wall and pit-below rule removed | 1128, no flag (smoke run, noop 0 sigma 0); trigger angle 43.6 deg | 0 (smoke) | Pit 1: take-off 15 px from the edge, A held 6 frames, theta falls as the eye rises (23 deg over the gap), TTMn < threshold, hop too short (`runs/S3_robustness.md`) | `clips/S3_real_run.mp4` |
| S3 robustness: real wiring on HOLDOUT | 2026-10-18 | Part 6b HOLDOUT list, senses v2 + motor v2, default knobs | mean max_x 1156, min 1127 | 0/10 | 9/10 die in pit 1 (x 1127-1128), 1 in pit 2 (1414); 3 distinct (max_x, death x) | `clips/S3_death_pit1.mp4` |
| S3 controls (same senses/motor/knobs, 10 episodes) | 2026-10-18 | shuffles x5, theta-rule (43.6 deg), blind timer | theta-rule mean 1155; shuffles 0-3: 40 (never walk); shuffle 4: 2588; timer 298 | theta-rule 0/10; shuf4 8/10 (INVALID: A down 96% in silence); others 0/10 | Real wiring = theta-rule on this data (same pit-1 death); no evidence the wiring matters | `runs/S3_robustness.md` |
| S3b: pit = base + scaled tower | 2026-10-18 | Pit = BASE (the hole) + TOWER (16 px over the midpoint, height min(W, 68)) treated like a pipe face; replaces the true-angle hole (`flyrun/SPEC.md` B9, `runs/S3b.md`) | 1414, no flag (smoke run, noop 0 sigma 0, default knobs); no HOLDOUT (needs a flag) | 0 | Pit 1 crossed in 1 jump (take-off 29 px, 0.75 W = 24). Pit 2 (W 48): take-off 42 px (0.75 W = 36), released at the apex when the tower fell to 0, landed ~10 px short, fell in at x 1414 | `clips/S3b_run.mp4` |
| S3b: pipe 4 diagnosis (no fix) | 2026-10-18 | Pipe 4 reads 64 px | — | — | Jump 1 takes off 70 px out, apex 68 up at 30 px from the face, arrives falling (feet 134); jump 2 from the foot, peak 64, lands on top | `runs/S3b.md` |
| S3c: tower on the far edge + no flicker | 2026-10-18 | Pit tower moves to the far edge (height min(W, 68)); once released mid-air it stays 0 until landing (`flyrun/SPEC.md` B9, `runs/S3c.md`) | 2469, no flag (smoke run, noop 0 sigma 0, default knobs); no HOLDOUT (needs a flag) | 0 | Pits 1 and 2 crossed in one jump each (take-off 6 / 11 px before the near edge, landed 1164 / 1436). Pit 3 (between two 64 px stair tops): tower anchored to the floor is below his feet -> height 0 -> nothing looms, he walks in at x 2469 | `clips/S3c_full_run.mp4` |
| S3c: pipe 4 jumps (no fix) | 2026-10-18 | unchanged | — | — | Jump 1 from 70 px out, A 41 frames, lands at the foot (x 899); jump 2 from 2 px, A 27, lands on top (x 900) | `runs/S3c.md` |
| S3d: tower anchored to the highest rim | 2026-10-18 | Pit tower top = min(near rim y, far rim y) - min(W, 68); rims = tops of the solid columns at both edges (`flyrun/SPEC.md` B9, `runs/S3d.md`) | **3161, reaches the flag** (smoke run, noop 0 sigma 0, default knobs, unassisted) | 1 (smoke) | Pit 3 (between staircases) now crossed in one jump (take-off 6 px, landed 2518); pits 1, 2 unchanged (6 / 11 px). Pipe 4 still 2 jumps (no fix) | `clips/S3d_full_run.mp4` |
| S3d HOLDOUT: real wiring vs theta-rule | 2026-10-18 | Part 6b list, v2 senses + motor, default knobs; theta-rule trigger 43.6 deg | real: mean max_x 1832; theta-rule: 2754 | real **0/10**, theta-rule **8/10** | Real fly: 8/10 die at x 1804 (Goomba pair; jump peaks 34 px up), 1 pit 2 (1415), 1 pit 3 (2474). Theta-rule: 2 die in pit 1 (1127). Traces `runs/S3d_holdout_*.csv` | `runs/S3d.md` |
| S3e: cleared enemy hands over | 2026-10-18 | Enemy cleared (feet >= its top AND over it) drops out until landing, so G2 of a pair is chosen mid-jump (`flyrun/SPEC.md`, `runs/S3e.md`) | **3161, flag** (smoke, noop 0 sigma 0) | 1 (smoke) | Pair at x 1769-1810: box switches to G2 at frame 1071, A released at 1072, G2 stomped, landed x 1833. S3d oddity explained: G2 stomped (state 4), G1 behind -> threat none, correct | `clips/S3e_full_run.mp4`, `clips/S3e_pair.mp4` |
| S3e HOLDOUT: real wiring vs theta-rule | 2026-10-18 | Part 6b list, v2 senses + motor, default knobs | real mean max_x 2958; theta-rule 2812 | real **9/10**, theta-rule **8/10** | Real: 1 death (pit 1, x 1128, sigma 0.05). Theta-rule: 2 (pit 2, x 1418 / 1410). No Goomba-pair deaths. Wiring at most +1 episode over the rule | `runs/S3e.md` |
| O0 facts | 2026-10-18 | Facts for the ?-block / mushroom scenes (no behaviour code): JO -> GF, ORN -> DNa, motor leftward check, 1-1 ? blocks + mushroom RAM, enemy removal, M2 setup, baseline (`runs/O0_facts.md`) | — | — | JO: 20 auditory neurons hit the GF directly (689 syn); +20 neurons -> JO alone presses A from level ~6.5; the full k/N set (854 new) kills the looming trigger. Smell: ipsilateral steering (left antenna -> Left) but saturates at steer -0.0104 vs threshold -0.01 against HOME_R. Left motion: Left alone, x 280 -> ~180. Baseline fly never hits a ? and never turns back | `clips/O0_mushroom.mp4`, `clips/O0_m2_setup.mp4` |

**Controls** (not the real fly):
- Part 4b: theta rule 2056 mean / 0 flags, evolved timer 2469 (pit 3), fixed timer 1138 (`runs/004_robust.md` §1, §3).
- Part 5: first shuffle, 298 (Goomba #1) at the 4b genome; evolved on it 1262 (`runs/005_controls.md`) — withdrawn as unfair by audit `runs/006_audit.md`.
- Part 6b (fair shuffle, `runs/007_fixes.md`): shuffles 1784 / 2470 / **3161 (flag 10/10)**, evolved timer 2469, theta rule 2056. The shuffles that go far do it as free-running A timers (A held ~half of all frames with nothing in view), not as escapes.
- 7e reference (not a candidate): best infeasible genome, 1788.4 mean, 0 flags, 9–10 blind presses (`runs/008e_full_search.md` §3).

**7e death, where he dies now** (`clips/P_current_death.mp4`, 2.5 s at 0.5× speed, HOLDOUT noop 3 σ 0, x 1400→1532, replay asserted to give the logged max_x 1532): Mario jumps over the first Goomba, then descends with it **behind** him (dx −10 at the last frame; the logged cause is "enemy dx=−12") while a second Goomba is **12 px ahead** (dx +12), so he lands between two. Fix 1's extra RAM reads (`runs/009_fix1.md`) show he stomped the one behind (state change + bounce) and was killed by the one ahead.

## What's invented (`flyrun/knobs.py` INVENTED; none comes from the connectome)

- `G` (evolved): global recurrent gain
- `TTMN_THRESH` (evolved): TTMn activity that triggers A
- `A_HOLD` (evolved): frames A is held once triggered (a forced hold, CONTROL_AUDIT.md)
- `COOLDOWN` (evolved): frames A is refused after a hold
- `HOME_R` (evolved): constant rightward drive into LC10a-R every frame: the direction of travel is ours
- `PIT_GAIN` (evolved): scale of the pit cue
- `THETA_RULE_DEG` (evolved): no-brain baseline's threshold (theta arm only)
- `PIT_SENSE` (fixed): the PIT CUE: a pit has no face, so its width is fed to LC4/LPLC2 as a looming angle
- `PIPE_SENSE` (fixed): pipe/wall faces fed to LC4/LPLC2 as a looming angle (face height used as width)
- `W_ENEMY` (fixed): Goomba width used in theta = 2 atan(w / 2d)
- `STIM_COMBINE` (fixed): 'sum': every visible object adds its theta and |dtheta|
- `SENSOR_NOISE` (fixed): multiplicative Gaussian noise on the LC4/LPLC2 inputs (0 for display runs, 0.05 TRAIN/HOLDOUT)
- `NOISE_MODE` (fixed): 'common': one noise draw per frame for the whole population
- `ALPHA` (fixed): leak/mix rate of the rate update
- `CLIP` (fixed): activity ceiling
- `SUBSTEPS` (fixed): network steps per game frame
- `DNP09_THRESH` (fixed): DNp09 activity that means 'walk right'
- `STEER_THRESH` (fixed): |DNa_R - DNa_L| needed to steer
- `BLIND_PX` (fixed): blind-press metric distance
- `BLIND_PENALTY` (fixed): fitness penalty per blind press
- `FLAG_BONUS` (fixed): fitness bonus for the flag
- `SPAM_FIXED_HOLD/COOLDOWN` (fixed): spam_fixed baseline cadence 18/3
- `RANDOM_A_P` (fixed): right_randA baseline P(A)
- `SCRIPT_HOLD` (fixed): scripted driver jump length (assisted tests only, never in fitness)
- `tile IDs / rows (level.py)` (fixed): SOLID_WALL {18..21, 97}, ground rows 11-12, empty 0: hand-identified on 1-1 (run 001 notes); meaning unverified on other levels
- `W_steer construction` (fixed): cast choice, top-40 LC10a->DNa intermediates, predicted-NT signs, row-normalisation (tutorials/20_steering.ipynb)

## Rules from now on
- Every part adds one row to this table.
- Every part ends with a ≤ 20 s clip of where he dies now.
- At most 2 more fixes, then the video gets made with whatever result we have.
