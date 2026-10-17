# 004 robust and selective evolution (flyrun, part 4b)

Question: after training on noisy, shifted episodes with a penalty for blind presses, is the fly selective (few presses with nothing near) and does it beat a timer (spam) and the theta rule on HOLDOUT episodes it never trained on?

**Short answer: no on selectivity, marginal on distance, no on flag.** Numbers: `004_report_numbers.json`, `004_spam_baseline.json`, `004_reference_split.json`. Logs: `evo4/<arm>/all_evals.csv`, `gen.csv`. Videos: `evo4/<arm>/best.mp4` (HOLDOUT noop_start 3, sigma 0) and `evo4/<arm>/montage.mp4`.

## Setup

- **TRAIN** (what evolution sees): noop_start {0, 7, 17} with sigma 0.05, seeds 1, 2, 3 (paired in that order); fitness = mean over the 3 episodes of `max_x + 10000 flag_get - 50 blind_presses`.
- **HOLDOUT** (never seen in training): noop_start {3, 11, 25, 33, 41}, seeds 101 to 105, each at sigma 0 and sigma 0.05, so 10 episodes.
- Blind press = an A onset with no enemy, pipe face or pit within 60 px ahead (ground truth from RAM and the tile buffer, counted for every arm the same way).
- Noise applies to every arm's input: the fly's LC4/LPLC2 inputs, and the theta rule's theta (the same noise factor the LPLC2 input received, same rng stream). The spam arms sense nothing, so noise cannot touch them. (This changes the theta rule's behaviour at sigma > 0 compared with part 3, where it read clean theta.)
- CMA-ES as in part 4 (popsize 12, sigma0 0.25, up to 40 generations, 3 restarts, stop on 10 generations without improvement or flag on every TRAIN episode). Fly restarts: 1 = part 4 default genome, 2 = part 4 flag genome (restart 3 of part 4), 3 = fresh random start (seed 99). Spam arm: (A_HOLD, COOLDOWN) only, from 12 / 10.
- **Wall-clock:** 1862 s (31 min) in all: spam 757 s, theta 629 s, fly about 476 s (derived as the total minus the other two). The process crashed on the very last `state.pkl` save (a transient Windows `PermissionError` on the file replace) after all three fly restarts had finished; I added a retry to `_save` and marked the fly state done by hand, with no generation re-run. Holdout evaluation and videos took about 4 more minutes.

## 1. Spam baselines (before evolving)

| arm | TRAIN fitness | HOLDOUT mean / min max_x | A_frac | blind presses per episode | end |
|---|---|---|---|---|---|
| spam_fixed (Right, A hold 18 + cooldown 3, no sensing) | 188 | 1138 / 1138 | 0.84 | 19 of 39 onsets | dies in pit 1, every episode |
| spam_evolved (CMA over A_HOLD, COOLDOWN) | 1169 | 2469 / 2469 | 0.72 | 26 of 56 | dies in pit 3 (x 2448), every episode |

The fixed timer reaches only pit 1. The evolved timer, with hold 21 and cooldown 8, gets to pit 3 (x 2469), the same wall that stopped the part 4 theta rule. So "a timer is enough" is true up to pit 3 and false beyond it. All three spam restarts converged on exactly the same genome.

## 2. Best genome per arm

| arm | genome | TRAIN fitness (mean max_x, flag rate, blind) |
|---|---|---|
| fly (restart 3, fresh start) | G .824, TTMN .282, hold 31, cool 6, HOME_R .653, PIT_GAIN 2.50 | 4878 (2378, 1 of 3 episodes, 16.7) |
| theta rule (restart 1) | theta* 47.0 deg, hold 24, cool 1 | 2219 (2319, 0, 2.0) |
| spam_evolved | hold 21, cool 8 | 1169 (2469, 0, 26.0) |

Fly restarts: part 4 default start reached 4844 (12.7 blind), part 4 flag-genome start 4462 (13.7 blind), fresh start 4878 (16.7 blind). Every fly restart sits at flag on 1 of 3 TRAIN episodes with 12 to 17 blind presses per episode. Theta restarts: 2219, 1108 (this one settled on theta* 33.6 deg, cooldown 30), 2216. No best-genome knob is within 2% of a range edge, but two are close: the fly's A_HOLD is 31 of [4, 32] and the theta rule's COOLDOWN is 1 of [0, 30]; I did not widen any range.

## 3. HOLDOUT ranking (the headline table)

10 episodes each (5 at sigma 0, 5 at sigma 0.05). Ranked by HOLDOUT mean fitness. Rows marked ref are the part 4 genomes evaluated on the same episodes.

| arm | fitness | flag rate | mean / min max_x | A_frac | blind presses (of onsets) | where it ends |
|---|---|---|---|---|---|---|
| fly, part 4 hopper (ref) | 5878 | 0.5 | 2173 / 1127 | 0.73 | 25.9 (of 61.9) | sigma 0: flag in 5 of 5; sigma 0.05: dead by x 1127 to 1219 in 5 of 5 |
| theta rule, part 4b | 1956 | 0 | 2056 / 2010 | 0.42 | 2.0 (of 23) | Goomba cluster at x 2010 (9 of 10), pit 3 once |
| theta rule, part 4 (ref) | 1541 | 0 | 1656 / 679 | 0.39 | 2.3 (of 22.8) | dies at x 1657 at sigma 0, mixed at sigma 0.05 |
| fly, part 4b | 1537 | 0 | 2487 / 1421 | 0.71 | 19.0 (of 38.9) | Goomba at x 2754 (8 of 10), pit 2 (x 1421) twice |
| spam_evolved | 1169 | 0 | 2469 / 2469 | 0.72 | 26.0 (of 56) | pit 3 (x 2469), 10 of 10 |
| spam_fixed | 188 | 0 | 1138 / 1138 | 0.84 | 19.0 (of 39) | pit 1, 10 of 10 |

By sigma: the 4b fly has mean max_x 2754 at sigma 0 (min 2754) and 2221 at sigma 0.05 (min 1421); the part 4 hopper has 3161 at sigma 0 (flag) and 1185 at sigma 0.05. So re-training on noise bought robustness at sigma 0.05 (mean max_x 2221 against 1185) at the cost of the flag: the 4b fly no longer reaches it even without noise.

## 4. Death maps (display episode, noop_start 3, sigma 0)

| arm | stops at | cleared | not cleared | cause |
|---|---|---|---|---|
| fly 4b | x 2754 | everything through pit 3 (x 2448), the down-stairs and pipe 5 (x 2608) | pipe 6 (x 2864) onward | killed by a Goomba 8 px ahead; 44 presses, 21 blind; median gap between presses 37 frames |
| theta 4b | x 2010 | to the Goomba cluster at x about 2000 | the up-stairs (x 2144) onward | killed by a Goomba 6 px ahead |
| spam_evolved | x 2469 | pit 1, pit 2, stairs | pit 3 (x 2448) onward | falls in pit 3 |

Silence check on the 4b fly genome: no enemy, no pipe, no pit sensed, 600 frames: A_frac 0, TTMn max 0.014. So it is stimulus-driven, not a free-running oscillator, as in part 4.

## 5. Is the fly selective, and does it beat spam and the theta rule?

No on selectivity. The re-evolved fly presses A in 71% of frames and 19 of its 39 onsets are blind (49%); the spam timer is at 72% and 46%, and the theta rule at 42% and 9% (2 of 23). The blind-press penalty did not move it: with the flag bonus at 10000 and the penalty at 50 per press, 17 blind presses cost the fly about 850 while one flag in three TRAIN episodes was worth about 3300, so every fly restart settled for the hop-and-hope operating point. On the HOLDOUT its mean max_x (2487) is level with the evolved timer (2469) and 430 px beyond the theta rule (2056), but it reaches the flag in none of the 10 episodes, and the part 4 hopper remains the only genome that reached the flag (5 of 5 at sigma 0, none at sigma 0.05). It does beat the timer in one concrete place: the timer dies in pit 3 in all 10 episodes, while the fly crosses pit 3, the down-stairs and pipe 5 in 8 of 10 and dies to a Goomba at x 2754. That gap is what the sensing buys; I attribute it to the pit cue (the evolved PIT_GAIN is 2.5, against 1.0 for the theta rule), but I did not test that by zeroing it. It loses to the theta rule on the blind-press count and so on the penalised fitness (1537 against 1956). Where they differ: the theta rule is the only selective arm and is stopped by the Goomba cluster at x 2010; the timer is stopped at pit 3; the fly is stopped at the Goomba at x 2754; none gets past x 2754.

What this does not support: the claim that the connectome circuit finds selective, noise-robust escape-jump timing on its own. What it does support is narrower: the circuit as a sensor front-end plus a threshold on TTMn gets past pit 3, which a blind timer and the part 4 theta rule do not, but it does so while pressing A as often as the timer.

## Changes made this part

`episodes4.py` (TRAIN, HOLDOUT, aggregate), `evolve4.py`, `report4.py`, `genome.py` (spam arm), `baselines.py` (Spam, SpamFixed; the theta rule reads the noisy theta), `senses.py` (`Loom.theta_noisy`), `run.py` (blind_presses, n_onsets, a_frac in every summary), `fitness.py` (`blind_penalty` option, off by default so Part 1 to 4 numbers are unchanged), `evolve.py` (retrying `_save`). The shuffle was not run (part 5).
