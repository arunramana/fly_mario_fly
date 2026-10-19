# E2 pre-registration: evolution Stage 2 - all the knobs that are CHOICES, from the E1s best, 1-1 only (written and committed BEFORE the search starts; base 82dba44)

No rule change; facts (RAM measurements, sizes, the 68 px apex, SUBSTEPS) never evolve. Four geometry choices that were hard-coded constants became Knobs with defaults equal to the old values (`PIT_TOWER_POS` 1.0, `PIT_TOWER_H` 1.0, `HUM_REACH_PX` 64, `EYE_DY` 0): **check: the E1s best genome on 1-1 HOLDOUT with the new code reproduces E1s exactly (10/10 trajectory hashes and scores equal)**.

## 1. Genome (16 genes, `configs/genome_e2.yaml`, `flyrun/e2_genome.py`; the same 5 drives on, headroom on, the 907 sour brain)
| group | gene | start | bounds | scale |
|---|---|---|---|---|
| E1s gains | HOME_R | 0.46496 | [0.11624, 1.85983] | log |
| | HUM_GAIN | 15.25328 | [13.60565 (floor), 61.01312] | log |
| | SMELL_GAIN | 401.53278 | [100.38319, 1606.13112] | log |
| | SOUR_GAIN | 4.90947 | [4.3305 (floor), 19.63789] | log |
| motor | TTMN_THRESH | 0.09921 | [0.04961, 0.14882] | linear |
| | RELEASE_THRESH | 0.08315 | [0.04158, 0.12473] | linear |
| | STEER_THRESH | 0.00947 | [0.00473, 0.0142] | linear |
| | MDN_THRESH | 0.10905 | [0.05453, 0.16358] | linear |
| | DNP09_THRESH | 0.05 | [0.025, 0.075] | linear |
| brain dynamics | G | 0.5 | [0.25, 0.75] | linear |
| | ALPHA | 0.3 | [0.15, 0.45] | linear |
| | CLIP | 50 | [25, 75] | linear |
| box geometry (perception choices, orange) | PIT_TOWER_POS (0 = near edge ... 1 = far edge) | 1.0 | [0, 1] | linear |
| | PIT_TOWER_H (x min(W, 68)) | 1.0 | [0.5, 1.5] | linear |
| | HUM_REACH_PX | 64 | [48, 80] | linear |
| | EYE_DY (eye lowered from the top-front corner, px) | 0 | [0, 16] | linear |
Start = the E1s best (generation 8 of `runs/E1s_progress.json`) + the current values of the new genes. The E1s genes keep their E1s rules and floors (`runs/E1s_floors.json`: HUM 13.6057, SOUR 4.3305; the rule 1/4 x..4 x of the start raised to the floor, thresholds +-50%, now around the E1s best). Two start values sit on a bound (PIT_TOWER_POS 1.0 at the top, EYE_DY 0 at the bottom): CMA-ES works on the unit cube with bounds. SUBSTEPS fixed.

## 2. Fitness, safety, training: unchanged from E1s
`max_x / 3161 + score / 10000` per episode, candidate = the mean over the 12 training episodes (noop 0, 7, 15, 19, 29, 37 x sigma 0 and 0.05; seeds 301-312); safety: any grounded A onset with no loom threat and no hum in any training episode rejects the candidate (fitness -1). No flag bonus. HOLDOUT never in training.

## 3. Budget
CMA-ES (`cma` 4.5.0), unit cube, sigma0 0.2, seed 1, **population = the CMA default for 16 genes = 12** (4 + floor(3 ln 16)), **<= 40 generations, patience 10** (stop after 10 generations without improvement of the best-ever, > 1e-9), 14 workers. **Timing:** one full flag episode of the start genome (noop 0, sigma 0, 2349 frames) takes **10.1 s**; a generation is 144 episodes / 14 workers: <= 1.7 min (worst case); 40 generations <= **1.2 h**, far under 12 h, so the full budget is used. (E1s's 45 s per episode was inflated by a stray process that I had left running; its search times were not affected after I removed it.)

## 4. The test, run ONCE on the E2 best AND the E1s best (same episodes), no retuning after
- 1-1 HOLDOUT (noop 3, 11, 25, 33, 41 x sigma 0 / 0.05, the usual 10).
- A HARDER set: **20 new start timings at sigma 0.1** (noop_start 79, 97, 113, 127, 137, 151, 157, 167, 173, 179, 181, 197, 199, 211, 223, 227, 229, 233, 239, 241; noise seeds 701-720). Never used in any earlier episode list (a grep of the flyrun code, notes and logs for these numbers in a "noop" context found none).
- Reported: flags, mean max_x, mean score, "?" blocks, mushroom eaten, back-up presses, deaths (x + cause); the 1-2 opening (noop 0, sigma 0) once, information only.
- Reported honestly if E2 is no better than E1s.
- Logs / clips after: per generation the best / mean fitness, the best genome and its noop 0 sigma 0 run; `runs/E2_genes.png`; `clips/E2_best_full.mp4`, `clips/E2_vs_E1s.mp4` (the most interesting difference), `clips/E2_geometry.png` (old vs new pit tower / hum reach, if the geometry moved), `clips/E2_12_opening.mp4`.

## Amendment (2026-10-19, after the search and after seeing the pre-registered test; logged BEFORE the extra set is run)
The pre-registered HARDER set turned out to be mostly a harness artifact: the episode loop ends a run as "stuck" when 150 frames pass without progress, and with a noop start of 151 or more that rule fires during the wait, before the fly has acted (max_x 40, "stuck (open ground)"): **15 of the 20 pre-registered timings (151-241) end that way for BOTH genomes**, so only 5 of the 20 (noop 79-137) test anything. The pre-registered result is reported as it is (E2: 3/20 flags, E1s: 5/20), together with this explanation, and **one extra set is run once, with the same procedure, for both genomes: 20 NEW timings below 150 (never used before), sigma 0.1, seeds 801-820**: noop_start 55, 59, 81, 91, 93, 95, 99, 111, 115, 119, 121, 123, 129, 133, 135, 141, 143, 145, 146, 147. It is labelled as an amendment, not a replacement. No other change.
