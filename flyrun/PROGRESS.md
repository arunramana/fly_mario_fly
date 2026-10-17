# flyrun — PROGRESS (the scoreboard)

## Where we are
The best honest result is Part 4b's evolved fly: mean max_x **2487** on the 10 held-out start timings, but **0 flags**. Real-fly flags on held-out episodes so far: the Part 4 "hopper" (5 of 10: all five at σ 0, none at σ 0.05), Part 6b's r3 (1 of 10), and one 7d TRAIN genome that is infeasible (3 of 6 TRAIN). The strict Part 7 rules (silent when nothing is in view, first jump at a Goomba, ≤ 8 blind presses) pushed the best result down to **1629** (7e, 0/10 flags): Mario now clears the floating-ledge Goomba at x≈1220 but dies at x 1532 landing between two Goombas (7 of 10 episodes). Next: by the pre-registered rule (7e) the fallback is to make floating block rows visible as obstacle faces (a new labelled sense, then redo 7d → 7e) — waiting for Arun's go.

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

**Controls** (not the real fly):
- Part 4b: theta rule 2056 mean / 0 flags, evolved timer 2469 (pit 3), fixed timer 1138 (`runs/004_robust.md` §1, §3).
- Part 5: first shuffle, 298 (Goomba #1) at the 4b genome; evolved on it 1262 (`runs/005_controls.md`) — withdrawn as unfair by audit `runs/006_audit.md`.
- Part 6b (fair shuffle, `runs/007_fixes.md`): shuffles 1784 / 2470 / **3161 (flag 10/10)**, evolved timer 2469, theta rule 2056. The shuffles that go far do it as free-running A timers (A held ~half of all frames with nothing in view), not as escapes.
- 7e reference (not a candidate): best infeasible genome, 1788.4 mean, 0 flags, 9–10 blind presses (`runs/008e_full_search.md` §3).

**7e death, where he dies now** (`clips/P_current_death.mp4`, 2.5 s at 0.5× speed, HOLDOUT noop 3 σ 0, x 1400→1532, replay asserted to give the logged max_x 1532): Mario jumps over the first Goomba, then descends with it **behind** him (dx −10 at the last frame; the logged cause is "enemy dx=−12") while a second Goomba is **12 px ahead** (dx +12), so he lands between two. The logged columns do not say which of the two touched him.

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
