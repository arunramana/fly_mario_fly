# 008d — Part 7d short search (flyrun, assisted, disclosed)

Stamp: commit ac2e1b699a, config 54051be754ef, W 5c57f81f5b1d, python 3.12.6, pip-freeze ba762955ba14  (search ran at commit ac2e1b6 on a clean tree; config amended to 10 gens/restart, see `008_preregistration.md` Amendment 2)

**Answer to the key question: for the warm-r3 restart, yes. The best genome's six TRAIN episodes all pass x≈1220 (min max_x 1409). The fresh-97 restart's best does not: 4 of its 6 TRAIN episodes still die at x 1223–1225 (the same ledge). No flag on any feasible genome in either restart, so the fallback is not triggered by the pre-registered condition, but 7d did not produce a win either.**

Setup: TRAIN only (6 episodes + 1 silence run per genome), 16 genomes x 10 gens per restart, CMA seeds 71 (warm r3) and 73 (fresh rng 97), constraints enforced (fitness -inf on any failure; CMA is told a graded value below every feasible one, see `search7.py` docstring). HOLDOUT not touched. Wall: 27.1 min (warm r3) + 22.3 min (fresh 97). Outputs: `evo7d/<restart>/{gen.csv,all_evals.csv,best_genome.json,state.pkl,stamp.json}`, `evo7d/warm_r3/montage.mp4` (gen 0 and gen 6, the only improving generations).

## Per restart

| | warm r3 | fresh rng 97 |
|---|---|---|
| best TRAIN fitness | **1589** (gen 6; r3's own start 1131) | **1161** (gen 9) |
| best genome TRAIN mean / min max_x | 1798 / 1409 | 1411 / 1223 |
| TRAIN flags (of 6) | 0 | 0 |
| mean blind presses | 4.2 | 5.0 |
| genomes evaluated / feasible | 160 / 91 (57%) | 160 / 69 (43%) |
| feasible by generation | 3,1,3,9,8,10,13,14,14,16 | 0,5,3,6,4,8,8,9,11,15 |
| improved best at gens | 0 (start), 6 | 1, 8, 9 |

**Rejections (all evaluated genomes; reasons can combine).** warm r3, 69 rejected: first_a only 28; first_a+silence 12; blind+first_a 11; blind+first_a+silence 10; blind only 8. fresh 97, 91 rejected: first_a only 57; first_a+silence 27; blind+first_a+silence 4; blind+first_a 3. "First A at a threat" (first A with stim_d <= 60 px) is the binding constraint: it is in 61/69 and 87/91 of the rejections. Silence failures: 22 and 31 genomes (always with first_a).

One notable infeasible genome: warm r3 gen 8 idx 2 reached the **flag on 3 of 6 TRAIN episodes** (max_x 3161 x3, others 826 / 1412 / 824) but is rejected for blind presses (mean 8.3, a per-episode limit of 8 exceeded). Its genome: G .747, TTMN_THRESH .367, A_HOLD 17, COOLDOWN 4, HOME_R 1.56, PIT_GAIN 1.83. Not selected (constraints are pre-registered); recorded as information.

## TRAIN death map of the best genome (episodes: noop 0,7,17,22,29,36 at sigma 0.05)

warm r3 best (gen 6): max_x / end per episode: **1805** enemy (dx -14); **2010** enemy (dx 9); **1409** pit; **2015** enemy (dx 8); **1532** enemy (dx -12); **2015** enemy (dx 8). First A at stim_d 20–22 px, blind presses 4–5 per episode.
r3's own start genome on the same episodes: 2469 (pit), 1220, 1220, 1222, 1137 (pit), 1220: four of six at the ledge or earlier.
fresh 97 best (gen 9): 1223 (enemy dx 9), 1225 (dx 6), 1225 (dx 6), 1783 (dx 9), 1225 (dx 6), 1783 (dx 9). First A at 45-51 px, blind 4–7.

## Knob drift vs r3 (start -> warm-r3 best | fresh-97 best, for reference)

| knob | r3 | warm-r3 best | fresh-97 best |
|---|---|---|---|
| A_HOLD (4–32) | 18 | **20** (+2) | 32 |
| COOLDOWN (0–30) | 2 | **10** (+8) | 23 |
| TTMN_THRESH (.02–.4) | .295 | .279 (-.016) | .121 |
| G (.2–1.5) | .711 | .678 (-.033) | .664 |
| HOME_R (.1–2) | 1.684 | 1.605 (-.079) | .639 |
| PIT_GAIN (0–5) | 1.360 | **2.161** (+.80) | 3.897 |

The warm-r3 best moved mainly COOLDOWN (2 -> 10), PIT_GAIN (+0.8) and A_HOLD (+2); the 7b-expected levers moved, but I did **not** ablate, so I cannot say which of the changes cleared the ledge, and the result is a single best genome of one restart with 6 noisy TRAIN episodes.

## What we learned / caveats

- The search found a TRAIN genome that clears the ledge (warm r3, gen 6) and the improvement is +458 fitness over r3's start; it still does not reach the flag (deaths at 1409–2015: a pit and Goombas later in 1-1).
- Ledge-clearing is not rare among evaluated genomes: min max_x > 1220 on 10 warm-r3 genomes (4 feasible) and 3 fresh-97 genomes (2 feasible), but gen 7–8 show it is not stable under CMA's sampling (gen-best mean_max_x fell back to 1189 / 1320, min 678 / 296).
- A genome can reach the flag on TRAIN only by breaking a constraint (gen 8 above): the constraints, mainly blind presses, bind where the flag is.
- Not evaluated on HOLDOUT (by design). 10 generations is a short search and the best was last improved at gen 6 (warm) / gen 9 (fresh, still improving), so 7e's longer budget is the test.
- Montage: `evo7d/warm_r3/montage.mp4` replays the run-best genome of each improving generation on TRAIN episode 0 (noop 0, seed 1): gen 0 ends in a pit at x 2469, gen 6 ends at an enemy at x 1805. (mp4 is gitignored.)
