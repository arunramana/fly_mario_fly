# E1s: evolution Stage 1 WITH sour smell on 1-1 (pre-registered in `runs/E1s_prereg.md`, commit 572a18d; 907-neuron sour brain, headroom looming ON; no rule or perception change)

**Result: on HOLDOUT (run once) the E1s best genome reaches the flag in 10/10 episodes (E1: 8/10, AV1 both-on: 8/10), mean max_x 3161 (all flags), mean score 2275 (E1 1940, AV1 3485), 2.7 "?" blocks per episode, a mushroom eaten in 8/10, 87 back-up presses in 10 episodes (8.7 per episode; AV1: ~11), no stall and no A press with nothing in view. It is better than E1 on flags, max_x and score, and below AV1's score (3485 against 2275); the training fitness of its best genome (1.171) is lower than E1's (1.226).** Post-hoc ablation (back-up nearly off) gives 8/10: the two lost episodes die at x 1220-1221, the old hum + Goomba death, so the sour smell is what removes that death here.

## 1. Floors (re-measured on the 907 brain, `runs/E1s_floors.json`)
HUM_GAIN **13.6057**, SMELL_GAIN 6.452, HOME_R 0.1003 (all three identical to the 881-brain floors), **SOUR_GAIN 4.3305** (the smallest gain at which the AV1 Koopa scene still backs up, >= 5 back-up frames; start 8.0587). Bounds used: HOME_R [0.1134, 1.8142], HUM_GAIN [13.606, 54.765] (the floor is the lower bound), SMELL_GAIN [109.86, 1757.7], SOUR_GAIN [4.3305, 32.235] (the floor is above 1/4 x = 2.01), thresholds +-50%.

## 2. The search (population 12, CMA seed 1, 14 workers; 17 generations, stopped by the 8-generation patience rule; generation times 81-934 s, ~1.05 h in all; the timing projection was <= 3.9 h)
Start genome (E1 best + SOUR_GAIN 8.0587 + MDN_THRESH 0.10) on the 12 training episodes: fitness **1.011** (7/12 flags, mean max_x 2353, not rejected). No candidate was rejected by the safety rule in any generation.
| gen | best | mean | rejected | best genome: flags (train) | best mean max_x |
|---|---|---|---|---|---|
| 0 | 1.0867 | 0.6871 | 0/12 | 12/12 | 3161 |
| 1 | 1.0933 | 0.6718 | 0/12 | 12/12 | 3161 |
| 2 | 1.0758 | 0.4989 | 0/12 | 12/12 | 3161 |
| 3 | 1.0900 | 0.8230 | 0/12 | 12/12 | 3161 |
| 4 | 1.0633 | 0.7724 | 0/12 | 12/12 | 3161 |
| 5 | 1.0817 | 0.6749 | 0/12 | 12/12 | 3161 |
| 6 | 1.0767 | 0.7886 | 0/12 | 12/12 | 3161 |
| 7 | 1.0758 | 0.8696 | 0/12 | 12/12 | 3161 |
| 8 | 1.1707 | 0.8824 | 0/12 | 11/12 | 3025 |
| 9 | 1.0667 | 0.8962 | 0/12 | 12/12 | 3161 |
| 10 | 1.0653 | 0.8963 | 0/12 | 11/12 | 3025 |
| 11 | 1.0650 | 0.8024 | 0/12 | 12/12 | 3161 |
| 12 | 1.0767 | 0.9610 | 0/12 | 12/12 | 3161 |
| 13 | 1.0842 | 0.9554 | 0/12 | 12/12 | 3161 |
| 14 | 1.1050 | 0.9902 | 0/12 | 12/12 | 3161 |
| 15 | 1.0933 | 0.8878 | 0/12 | 12/12 | 3161 |
| 16 | 1.1042 | 0.9664 | 0/12 | 12/12 | 3161 |
Best-ever: **generation 8, fitness 1.1707** (11/12 training flags). As in E1 the best-of-generation fitness is a plateau (1.06-1.17) with one higher generation; the population mean climbs from 0.69 to ~0.96. `runs/E1s_genes.png` (gitignored) plots each gene over the generations.

## 3. Best genome vs the start
| gene | start | best | bounds |
|---|---|---|---|
| HOME_R | 0.4536 | **0.465** (1.03x) | [0.1134, 1.814] |
| HUM_GAIN | 13.69 | **15.25** (1.11x) | [13.61, 54.77] |
| SMELL_GAIN | 439.4 | **401.5** (0.91x) | [109.9, 1758] |
| SOUR_GAIN | 8.059 | **4.909** (0.61x) | [4.33, 32.23] |
| TTMN_THRESH | 0.1275 | **0.09921** (0.78x) | [0.06374, 0.1912] |
| RELEASE_THRESH | 0.09777 | **0.08315** (0.85x) | [0.04889, 0.1467] |
| STEER_THRESH | 0.01013 | **0.009467** (0.93x) | [0.005067, 0.0152] |
| MDN_THRESH | 0.1 | **0.1091** (1.09x) | [0.05, 0.15] |
What moved: **TTMN_THRESH went back down to 0.0992 (0.78x of the E1 value, about the original 0.10)**: with the sour back-up in place the higher jump threshold that E1 needed is not needed any more; SOUR_GAIN x0.61 (towards its floor), HUM_GAIN x1.11 (just above its floor), RELEASE_THRESH x0.85, MDN_THRESH x1.09, HOME_R, SMELL_GAIN (x0.91) and STEER_THRESH within 10%. (No ablation of single genes was run.)

## 4. HOLDOUT, run ONCE (`runs/E1s_holdout.json`; best-ever genome, enemies on)
| noop, sigma | flag | max_x | death | ? blocks hit (x) | mushroom out / eaten / big at end | score | back-up presses |
|---|---|---|---|---|---|---|---|
| 3, 0.0 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 1900 | 8 (109 fr) |
| 11, 0.0 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 1900 | 8 (109 fr) |
| 25, 0.0 | flag | 3161 | - | [336, 368, 1248, 1696, 1792] | 1 / 1 / 1 | 3850 | 10 (120 fr) |
| 33, 0.0 | flag | 3161 | - | [336, 368, 1248, 1696, 1792] | 1 / 1 / 1 | 3850 | 10 (120 fr) |
| 41, 0.0 | flag | 3161 | - | [336, 368, 1248, 1696, 1792] | 1 / 1 / 1 | 3850 | 10 (120 fr) |
| 3, 0.05 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 1900 | 9 (110 fr) |
| 11, 0.05 | flag | 3161 | - | [368] | 0 / 0 / 0 | 800 | 6 (34 fr) |
| 25, 0.05 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 1800 | 12 (118 fr) |
| 33, 0.05 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 2000 | 8 (109 fr) |
| 41, 0.05 | flag | 3161 | - | [368] | 0 / 0 / 0 | 900 | 6 (36 fr) |
| **total** | **10/10 flags** | mean 3161 | | mean 2.7 blocks | eaten 8 | mean 2275 | 87 (8.7 per episode) |
| E1 | 8/10 | 2890 | enemy x 1806 (2) | 3.6 | eaten 7 | 1940 | 0 |
| AV1 both on (E1 genome) | 8/10 | 2930 | enemy x 2743, stuck x 1251 | 5.1 | eaten 10 | 3485 | 108 (~11 per episode) |
Per-episode fitness on HOLDOUT (max_x / 3161 + score / 10000): E1s **1.227**, E1 1.108. No A press with nothing in view in any episode (0 violations), no stall (no episode ends "stuck"). Left presses 109 in total (back-up included). **Where it is worse:** the score (2275 vs AV1's 3485: it hits fewer blocks, 2.7 vs 5.1, and eats 8 mushrooms instead of 10), and the training fitness of the best genome is lower than E1's (1.171 vs 1.226); it is not worse than E1 on any HOLDOUT headline number.

## 5. Post-hoc ablation (NOT the official result): back-up nearly off
The best genome with SOUR_GAIN 4.3305 (its floor) and MDN_THRESH 0.15 (its upper bound), 1-1 HOLDOUT (`runs/E1s_ablation_holdout.json`): **8/10 flags**, mean max_x 2773, mean score 2130, 2.2 blocks, mushroom eaten 8, back-up presses 28 (not zero: the floor still backs up a little).
| noop, sigma | flag | max_x | death | ? blocks hit (x) | mushroom out / eaten / big | score | back-up presses |
|---|---|---|---|---|---|---|---|
| 3, 0.0 | flag | 3161 | - | [336, 368, 1248] | 1 / 1 / 1 | 2900 | 2 (80 fr) |
| 11, 0.0 | flag | 3161 | - | [336, 368, 1248] | 1 / 1 / 1 | 2900 | 2 (80 fr) |
| 25, 0.0 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 2200 | 4 (80 fr) |
| 33, 0.0 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 2200 | 4 (80 fr) |
| 41, 0.0 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 2200 | 4 (80 fr) |
| 3, 0.05 | flag | 3161 | - | [336, 368, 1248] | 1 / 1 / 1 | 3050 | 2 (80 fr) |
| 11, 0.05 | DIED | 1221 | 1221 enemy dx=8 | [368] | 0 / 0 / 0 | 300 | 1 (4 fr) |
| 25, 0.05 | flag | 3161 | - | [336, 368, 1248] | 1 / 1 / 1 | 3050 | 3 (81 fr) |
| 33, 0.05 | flag | 3161 | - | [336, 368] | 1 / 1 / 0 | 2200 | 4 (80 fr) |
| 41, 0.05 | DIED | 1220 | 1220 enemy dx=9 | [368] | 0 / 0 / 0 | 300 | 2 (6 fr) |
What sour adds in this setting: with it almost off, two episodes die again at x 1220-1221 (a Goomba under the hum block, the C1 death); with the evolved sour gain and threshold they do not (10/10).

## 6. The 1-2 opening (noop 0, sigma 0, once, information only; not part of the test)
The best genome dies at **x 891** (a Koopa, dx 8, 596 frames, score 400): the same place as the E1 genome in L2 (x 890); the sour back-up and the headroom looming did not get him past it. `clips/E1s_12_opening.mp4`.

## 7. Files and clips
`flyrun/configs/drives.yaml` (+ `drives_e1.yaml`), `e1s_genome.py`, `e1s_floors.py`, `e1s_evolve.py`, `e1s_log.py`, `e1s_ablation.py`, `e1s_clips.py`; `runs/E1s_prereg.md`, `E1s_floors.json`, `E1s_start.json`, `E1s_progress.json`, `E1s_holdout.json`, `E1s_ablation_holdout.json`, `E1s_E1s_gen<NN>_best.csv / .json` (the best genome of each generation, noop 0 sigma 0; rates npz local), `E1s_E1s_12opening.*`. Clips (R3 layout, gitignored): `E1s_best_full.mp4`, `E1s_vs_E1.mp4`, `E1s_backup_moments.mp4`, `E1s_12_opening.mp4`; the renderer now draws the sour marker as a dotted yellow box 4 px outside the red loom box, opacity ~ the sour level, and "yellow = sour" is in the colour key (title card, SPEC.md).
