# 007 fixes for the 006 audit (flyrun part 6b)

Numbers: `007_shuffle_feeders.json`, `007_default_knobs.json`, `007_fair_eval.json`, `007_silence.json`. Evolution logs: `evo6/<arm>/{gen.csv, all_evals.csv, best_genome.json}`, `evo6_log.txt`. Code: `shuffle.py`, `evolve6.py`, `fair_default.py`, `fair_eval.py`, `make_clips6b.py`, `tests/test_part6b.py`. Assisted, disclosed run; nothing here changes how the fly is driven.

## Per audit finding

| # | finding | status | evidence |
|---|---|---|---|
| 1 | shuffle destroyed input normalisation | **fixed** | `shuffle.py`: the swap runs on the synapse-count matrix (rebuilt from `steer_edges.parquet`; `build_W(counts, signs)` reproduces `W_steer.npy` bit-for-bit, asserted), then W is rebuilt with the notebook's rule. All 5 seeds (`W_steer_shuf{0..4}_rn.npy`): row \|sum\| = 1.0 exactly in every row (min = max = 1.0, was 0.006-3.55); degrees and source signs equal to the real matrix; no self-loops; `tests/test_part6b.py` (12 tests incl. row sums). Part 5's `W_steer_shuf0.npy` is kept untouched for the historical record (`--legacy`). |
| 5 | unequal evolution budget | **fixed** | `evolve6.py`: every arm (real, shuf0-2) = 3 restarts [default, fresh(rng 99), fresh(rng 98)], same CMA seeds 1-3, same TRAIN set, same fitness, no warm start from Part 4. The real arm was re-run in this layout (676 s) instead of reusing the 4b run, so budgets match exactly. The 4b original is shown separately as a reference. |
| 2 | HOLDOUT overstated | **fixed (reporting)** | `episodes4.aggregate` now returns `n_episodes` and `n_traj` (distinct (max_x, death x)); every Part 6b table, `numbers.md` and the card carry it. Wording is "held-out start timings", not "held-out levels". Older `runs/00x.md` files are historical and were not edited; `numbers.md` lists their distinct counts (real 4b: 2; hopper at sigma 0: 1; real default knobs: 1). There is still no held-out level; that is not fixed. |
| 3 | invented pieces not all in knobs / not disclosed | **fixed** | `BLIND_PX`, `BLIND_PENALTY`, `FLAG_BONUS`, `SPAM_FIXED_HOLD/COOLDOWN`, `RANDOM_A_P`, `SCRIPT_HOLD` moved to `knobs.py` (same values, behaviour unchanged: the existing flyrun tests pass and the real-matrix rerun reproduces 43.6 deg / 723 / 2487). Every `Knobs` field is tagged `INVENTED (evolved)` or `INVENTED (fixed)` (STIM_COMBINE, SENSOR_NOISE, NOISE_MODE, the pit cue, HOME_R included); a registry `knobs.INVENTED` is test-checked to cover every field. Tile IDs / rows in `level.py` are tagged "hand-identified on 1-1". `clips/numbers.md` has an "Invented pieces" section generated from the registry. |
| 4 | guard on one path only | **fixed** | `fitness._one` raises on any `driver == "script"` frame, so evolution, HOLDOUT and `evaluate()` are all covered. No-brain controllers are now logged `driver="baseline"` instead of `"fly"`. `test_fitness_one_rejects_scripted_frames` calls `_one` with `takeover_x` and expects the error. |
| 7 | 1-1 only | **disclosed, not fixed** | titles/captions say 1-1; tile IDs tagged hand-identified. No second level was tried. |
| 8 | clip 06 best-of-40 | **fixed** | Clip 06 is now the median HOLDOUT episode (max_x 2470) of the median shuffle seed (seed 1 of 0-2 by evolved HOLDOUT mean), banner says so on screen. Old clip kept as `06_shuffle_SUPERSEDED_best_of_40_part5.mp4`. |
| 9 | not reproducible | **fixed** | sha256 of every array/parquet used is in `numbers.md`; `flyrun/` committed without .npy/.mp4. |

## Results with the fair shuffle (HOLDOUT = 10 start-timing/noise episodes, level 1-1)

TTMn feeders after the fair shuffle (`007_shuffle_feeders.json`; real: both TTMn are fed only by a DNp01 at weight 1.0): every seed feeds one TTMn from an LC10a (not looming) and the other directly from a looming detector (LPLC2 in seeds 0, 1, 3, 4; LC4 in seed 2), also at weight 1.0. So the fair shuffle gives TTMn a shorter, stronger route from the detectors than the real wiring has.

Default knobs (`007_default_knobs.json`):

| matrix | theta at first A | TTMn peak | HOLDOUT mean max_x | distinct traj | looming escape at Goomba #1 | blind presses |
|---|---|---|---|---|---|---|
| real | 43.6 deg (at the Goomba) | 0.548 | 723 | 1 | yes, 10/10 | 2.1 |
| shuffle 0-3 | no A ever | 0.048-0.061 | 40 | 1 | no (never walks right) | 0 |
| shuffle 4 | 0 deg: A from frame 0, nothing in view | 0.612 | 723 | 1 | no: passes x 320 but not looming-driven | 12.0 |

Part 5's "TTMn 100x weaker" (0.548 vs 0.0013) becomes 0.548 vs 0.05-0.06 for seeds 0-3, so the effect shrinks from ~400x to ~10x once the normalisation confound is removed, and seed 4 has a TTMn as strong as the real one with no looming selectivity.

Evolved, equal budget (3 restarts each; `007_fair_eval.json`, `007_silence.json`):

| arm | HOLDOUT mean max_x | distinct traj | looming escape | blind presses | A held with nothing in view (silence test) | ends |
|---|---|---|---|---|---|---|
| real (best of 3) | 1172 (restarts: 1172 / 1937 / 1405) | 3 | 10/10 | 7.8 | 0% | Goomba |
| real, 4b original (reference, warm-started) | 2487 | 2 | 10/10 | 19.0 | 0% | Goomba x8, pit x2 |
| shuffle seed 0 | 1784 | 1 | 0/10 | 10.0 | 48% | Goomba |
| shuffle seed 1 | 2470 | 1 | 0/10 | 19.0 | 68% | pit 3 |
| shuffle seed 2 | 3161 | 1 | 0/10 | 25.0 | 52% | **flag 10/10** |
| evolved timer (no brain) | 2469 | 1 | 0/10 | 26.0 | n/a | pit 3 |
| theta rule (no brain) | 2056 | 2 | 10/10 | 2.0 | n/a | Goomba cluster |

The evolved shuffles reach the timer's distance or beyond (one reaches the flag) by driving G to 1.37-1.47: TTMn then saturates at the CLIP of 50 with nothing in view and A is held about half of all frames. Their first A has no Goomba in view in 30/30 episodes. They are timers, not escapes. The real evolved genome stays silent with no stimulus (A_frac 0, TTMn max 0.001) and fires only at the Goomba.

## Answer

With a fair shuffle, the real wiring still produces a stimulus-triggered looming escape at Goomba #1 at the default knobs (10/10 episodes, theta 43.6 deg) that 4 of 5 shuffles do not produce at all and the fifth (seed 4) fakes by pressing A from frame 0 with nothing in view, but on distance it does not beat the shuffle: evolved shuffles match or exceed it (1784 / 2470 / 3161 vs 1172) by becoming free-running A timers, so "wiring matters" is supported only for stimulus-selective triggering, not for how far Mario gets.

## Caveats

- 5 shuffle seeds at default knobs, 3 evolved: still a small sample, and the real arm's equal-budget best (1172) is lower than the 4b warm-started genome (2487), so the evolution outcome is noisy (restarts 1172-1937 for the real arm).
- "Looming escape" = first A fires with a Goomba in view and Mario passes x 320; it is a stimulus-triggering test, not a measure of how well the fly escapes.
- Level 1-1 only; HOLDOUT is start timing and noise.
