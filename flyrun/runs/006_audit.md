# 006 audit of flyrun/ before the public video

Auditor read the code first, the reports second. No code was changed. Scratch scripts are outside the repo.
Everything marked **(verified)** was checked against the files on disk or by re-running.

## Verdict

The scripted driver does **not** leak into fitness, HOLDOUT is **not** used in training, and noise is applied equally across arms. The three re-run numbers reproduce. But the headline claim, "the real wiring does what the shuffle does not", is **not supported as stated**. The shuffle control changes more than wiring (finding 1). The HOLDOUT set is not a held-out test (finding 2). The sensory and motor layers carry more invented structure than `numbers.md` discloses (findings 3 to 5).

## Findings, most severe first

### 1. HIGH: the shuffle also destroys per-neuron input normalisation, so "real vs shuffle" is confounded

- `shuffle.py:12-30` swaps edge *targets* and keeps each edge's weight on its source column.
- `W_steer` is **row-normalised**: `W_counts / row_sum * sign` (tutorials/20_steering.ipynb, Step 3). **Verified:** every real row has |sum| = 1.0 (min 0.99999, max 1.00000).
- After the shuffle, row |sums| run from **0.006 to 3.55**. Median is 0.93. 141 rows exceed 1.5 and 163 fall below 0.5. All 636 rows changed. In 76 rows the number of excitatory inputs changed, so the shuffle is out-degree and out-sign preserving, not "sign preserving" in general.
- The two TTMn neurons each have in-degree 1 in the real matrix, a weight of **1.0** from one DNp01 neuron. In the shuffle they get 0.055 (from an LC10a) and 0.006 (from an LPLC2). DNp01 gets row sums of 3.55 and 3.19. DNa01 gets 0.19 to 0.43.
- So the "TTMn response 100x weaker" (real peak 0.548, shuffle 0.0013; re-run) is largely the arithmetic of moving a weight-1.0 edge out of a 1-input row. It does not show that the fly's wiring is selective for looming. The 5 of 5 real-vs-shuffle failures at `shuf/part4b_fly` (298 max_x) have the same cause.
- **Fix:** add a row-renormalising degree shuffle (swap, then rescale each row to |sum| = 1), or shuffle *sources* within each target row. Re-run the real-vs-shuffle table with it. Until then, describe the control as "edge-swap shuffle that does not preserve input normalisation".
- Also note that `tests/test_part5.py:11-17` checks degrees and out-signs only, so no test would have caught this. Add `assert np.allclose(abs(S).sum(1), abs(W).sum(1))`.

### 2. HIGH: HOLDOUT is the same level and near-duplicate trajectories, so "never seen" overstates it

- `episodes4.py:10-12`: TRAIN and HOLDOUT are both SMB 1-1 (`env.py:24`). They differ only in the number of NOOP frames before takeover (0 to 41) and the noise seed.
- At sigma 0 the emulator is deterministic. **Verified** in `005_controls.json`: real 4b fly max_x = `[2754 x6, 1421 x2, 2754, 2754]`, so only two distinct outcomes in 10 episodes. Part 4 hopper is `[3161 x5, 1220, 1127, 1220, 1138, 1220]`. The shuffle is a single value (298) in all 10. The effective n is about 2 to 5 trajectories, not 10.
- The Part 4 hopper was evolved on one deterministic episode (`evolve.py:_eval_one`, seed 0, noop 0, sigma 0), and "flag 5 of 5 at sigma 0" is that same trajectory replayed with a 3 to 41 frame delay. Clip 05's banner discloses "deterministic / fails under 5% noise", which is honest. It must not be read as generalisation.
- The 4b fly (2487) is level with the evolved blind timer (2469) and above the theta rule (2056). The project's own 004_robust.md concludes "no on selectivity, marginal on distance, no on flag".
- **Fix:** say "held-out noise and start-delay, same level" everywhere. Add at least one held-out level or scene set, or report the number of distinct trajectories next to every HOLDOUT mean.

### 3. HIGH: `knobs.py` does not hold every invented scalar, and `clips/numbers.md` says nothing about invented pieces

- `knobs.py:1` claims "Every hand-set scalar for flyrun lives here and nowhere else." That is false. Hand-set values outside it, mostly unlabelled:
  - `run.py:17` `BLIND_PX = 60`. This defines the "blind press" metric used in the clips.
  - `episodes4.py:8` `BLIND_PENALTY = 50`, which shapes the evolved genomes.
  - `fitness.py:14` `FLAG_BONUS = 10000`.
  - `baselines.py:61` `A_HOLD=18, COOLDOWN=3` for `spam_fixed`. `baselines.py:26` `P_A` is labelled.
  - `scripted.py:10,22-25` has `HOLD = 28` plus the 28/22/30 px triggers. Labelled, and not in the fly path.
  - `level.py:17,22` `ROW_GROUND`, `SOLID_WALL = {18..21, 97}`, `TILE`. Found empirically on 1-1.
  - `senses.py:17` `max(d, 1.0)` clip, and the 256 px visibility window (`level.py:44`).
  - Upstream, in the tutorial notebooks: the top-40 intermediates choice, predicted-NT signs, and row-normalisation of W.
- `knobs.py:21-26` marks `STIM_COMBINE`, `SENSOR_NOISE`, `NOISE_MODE` as "FIXED", not "invented". They are invented.
- `clips/numbers.md` contains **no** mention of "invented". It lists the sources of the numbers on screen but does not say that the stimulus and the motor map are not from the connectome. The invented pieces are only listed in `005_controls.md` section 2.
- **Fix:** move the constants above into `knobs.py` (or a labelled `INVENTED` block), tag the three FIXED ones "invented (fixed)", and have `make_clips.py` append an "Invented pieces" table to `numbers.md`.

### 4. HIGH: the fly's behaviour depends on invented senses and a forced motor hold (the CLAUDE.md invariant 8 line)

- The Goomba loom is RAM geometry, as designed. But the **pipe face** (`senses.py:47-48`, face height used as "width") and the **pit** (`senses.py:49-51`) are invented looms fed to LC4/LPLC2. The pit has no face at all. `PIT_GAIN` is evolved over [0, 5] (`genome.py:11`).
- The pit-cue ablation (`005_controls.md` section 2) shows that setting `PIT_GAIN = 0` drops the 4b fly from 2487 to 1139. So the fly's whole advantage over a timer is the experimenter's pit cue passing through the circuit, not something the connectome detects.
- `HOME_R` (`senses.py:88`) is a constant rightward drive into LC10a-R on every frame, evolved over [0.1, 2.0]. The direction of travel is supplied by the experimenter, then read out as "walk right".
- `motor.py:8-29` `Muscle.press`: once TTMn crosses a threshold, A is held for `A_HOLD` frames (evolved 4 to 32) whatever the brain does, then refused for `COOLDOWN` frames. That is a forced hold and a cooldown (`CONTROL_AUDIT.md` lists these as violations to replace). The best 4b genome has `A_HOLD = 31` of [4, 32], at the range edge.
- None of these is hidden in the code, and all are labelled "invented" in `knobs.py`. The risk is the video narration, not the code.
- **Fix:** in narration and `numbers.md`, say "the circuit reads a pit/pipe stimulus we synthesised and walks right because we drive it right", and describe the motor stage as "threshold + held button".

### 5. MEDIUM: the shuffle-evolved arm got a smaller search budget than the real arm

- Real fly: 3 restarts (Part 4 default, Part 4 flag genome, fresh) (`evolve4.py:32`). Shuffle: 2 restarts, default and fresh (`evolve5.py:23`).
- The real arm's "restart 2" was seeded from the best Part 4 genome, which had already been evolved on the real matrix. The shuffle arm had no such head start. Per `005_controls.md`, restart 2 (fresh) gave the shuffle's best, so the missing restart may not matter, but it is not equal.
- **Fix:** give the shuffle the same three-restart layout (or drop restart 2 for the real arm) and report both.

### 6. MEDIUM: the "no scripted frames in fitness" guard is only on one path

- `fitness.py:71-73` raises on non-"fly" frames, but only in `evaluate()`. `evolve4.py:39` (training), `controls.py:33` (HOLDOUT) and `report4.py:44` call `pool.pool.map(_one, ...)` directly and never run the check.
- Today it cannot trigger on those paths, because their jobs do not pass `takeover_x`. **Verified** by reading `episodes4.jobs`: only `noop_start` and `blind_penalty` go through. The guard is just not enforced where it matters.
- Separately, `run.py:57` labels every non-scripted frame `driver="fly"`, including the no-brain baselines (`theta_rule`, `spam`). So `n_nonfly == 0` does not distinguish them either.
- **Fix:** move the `n_nonfly` check into `_one`, and set `driver="baseline"` when `controller is not None`.

### 7. MEDIUM: everything is level 1-1, with tile IDs and rows learned from 1-1

- `env.py:24` is 1-1 only. `level.py:17,22` use tile ID 97 for stair blocks, ground rows 11 to 12, and pit = both rows empty. These came from "run 001 notes", not from the game's spec. They will mis-read underground or castle levels.
- No level-specific x positions were found in the fly's runtime path. The x values in `controls.py:17` (`PIT3_CLEAR_X = 2480`) and `report4.py` are analysis-only. The scripted driver's constants are in `scripted.py` and only used for takeover tests.
- **Fix:** say "1-1" in the title and narration, and state that obstacle tile IDs are read from RAM but their meaning was found by hand.

### 8. LOW: clip 06 is selected from HOLDOUT, in the shuffle's favour

- `make_clips.py:196-208` shows the highest-max_x shuffle run out of 40. This overstates the shuffle, if anything, and is disclosed in `005_controls.md`. No fix needed beyond keeping the caption "best of 40".

### 9. LOW: the work is not under version control

- `git status` shows `?? flyrun/`, and `tutorials/_cache/W_steer*.npy` is gitignored. The numbers cannot be tied to a commit or a hashed matrix.
- **Fix:** commit `flyrun/`, and record the SHA-256 of `W_steer.npy` and `W_steer_shuf0.npy` in `numbers.md`.

## Checks that passed

| Item | Result |
|---|---|
| Scripted driver reaching fitness | No. `takeover_x` is only used from `controls_extra.py` and `levelmap.py`, outside fitness and HOLDOUT. |
| HOLDOUT used in training | No. `evolve4.py:17` imports only `TRAIN`. The `evolve5` run also uses TRAIN. HOLDOUT is used only for selection of display clips (finding 8). |
| Buttons pressed outside `motor.py` | `run.py:66` (NOOP before takeover), `run.py:61` (scripted, diagnostic only), and `baselines.py` (no-brain arms, labelled). All other actions come from `motor.decide`. |
| Forced jumps / per-scene knobs | None in the fly path. `knobs.py` holds one value per knob for the whole level. A hold and cooldown exist (finding 4). |
| Noise across arms | Equal. `run.py:40-41` builds one `Generator` per episode seed. The same seeds are used for real, shuffle, and baseline arms. The theta rule reads the same LPLC2 noise factor (`senses.py:85-86,89`). The spam arms sense nothing. |
| Shuffle degree-preserving | Yes: out-degree, in-degree, out-weight multiset per column, out-sign per column, no self-loops, no duplicate edges (**verified**, 29,961 edges before and after, 73 unmoved). Not input-normalisation preserving (finding 1). |
| Shuffle runs identical to real runs apart from W | Yes. `FLYRUN_WFILE` swaps only the matrix file (`brain.py:39`), and masks, bodies, knobs, episodes and seeds are identical. |

## Re-run of three numbers from `clips/numbers.md` / `005_controls.md`

| Number | Claimed | Re-run | Match |
|---|---|---|---|
| theta at first A, default knobs, sigma 0 | 43.6 deg (x 289) | 43.60 deg (x 289) | yes |
| TTMn peak, real vs shuffle (default knobs, closed loop, whole run) | 0.548 vs 0.005 (the 0.005 is from the assisted test) | 0.548 vs 0.0013 (closed loop, no first A) | yes for real. The shuffle is lower than quoted because the quoted 0.005 is from the assisted run, a different test. Both are far below the 0.10 threshold. |
| HOLDOUT mean max_x, 4b fly, real vs shuffle | 2487.4 vs 298.0 | 2487.4 vs 298.0 | yes |
| HOLDOUT mean max_x, default knobs, real vs shuffle | 723.0 vs 40.0 | 723.0 vs 40.0 | yes |

The numbers are reproducible. The problem is what they mean (findings 1 and 2), not whether they are right.

## Suggested wording changes for the video

1. Replace "wiring matters" with "this edge-swap shuffle breaks the circuit", until finding 1 is fixed and re-run.
2. Say "same level, new noise and start delay", not "held-out".
3. Say the pit and pipe stimuli, the rightward drive, and the A hold are chosen by us.
4. Say the fly roughly ties a blind timer on distance (2487 vs 2469).
