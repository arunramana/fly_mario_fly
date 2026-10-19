# E1 pre-registration: evolution Stage 1 on 1-1 (written and committed BEFORE the search starts; base 4151cdb, 881-neuron brain, current senses v2 / motor v2)

No rule or perception change. Everything not in the genome stays as it is (the current values = arm C).

## Genome (built from `flyrun/configs/drives.yaml` by `flyrun/e1_genome.py`)
Drives: looming ON (Goomba, Koopa, pipe faces, pit towers; no gain gene: its input is the angle), home ON, hum ON (reachable "?" blocks), smell ON (mushroom). Each ON drive with a gain contributes it; the motor thresholds are always in; an OFF drive's gain is not in the genome (evolution tunes, never switches off). With all four ON the genome has 6 genes:
`HOME_R, HUM_GAIN, SMELL_GAIN, TTMN_THRESH, RELEASE_THRESH (starts = TTMN_THRESH), STEER_THRESH`. Start = arm C: 0.5, 14.5342, 213.9495, 0.10, 0.10, 0.01.

## Bounds and floors (floors measured on the current brain, `runs/E1_floors.json`, `flyrun/e1_floors.py`; each a log bisection of a yes / no scene)
| gene | start | floor | measured how | bounds used |
|---|---|---|---|---|
| HUM_GAIN | 14.5342 | **13.606** (0.936 x start) | smallest gain at which hum alone (looming off) still hits block 256 in the Q2 scene | **[13.606, 58.137]** (the floor is above start/4 = 3.63, so the floor is the lower bound) |
| SMELL_GAIN | 213.9495 | **6.452** (0.030 x start) | smallest gain at which smell alone (home off) still gives a sustained turn (>= 5 Left frames) in the M2b scene A | [53.487, 855.80] (start/4 is above the floor) |
| HOME_R | 0.5 | **0.1003** (0.20 x start) | smallest value at which, with nothing in view, Right is pressed in >= 95% of frames 30-300 | [0.125, 2.0] (start/4 is above the floor) |
| TTMN_THRESH | 0.10 | n/a | | [0.05, 0.15] (+-50%) |
| RELEASE_THRESH | 0.10 | n/a | | [0.05, 0.15] (+-50% of its start) |
| STEER_THRESH | 0.01 | n/a | | [0.005, 0.015] (+-50%) |
Gains are log-scale (1/4 x to 4 x of start, raised to the floor), thresholds linear. Floors are bisected to ~1e-4 relative resolution and assume the pass condition is monotone in the gain from below. Note the hum floor is almost the start value: the hit window of block 256 is narrow, so the hum gain can only be raised in practice.

## Fitness and safety
- Per episode: `max_x / 3161 + score / 10000` (score = the game's end-of-episode score). Candidate fitness = the mean over the 12 training episodes. No flag or survival bonus.
- Safety: a candidate with ANY grounded A onset with nothing in view (no chosen loom threat AND no hum in the log) in ANY training episode is rejected: fitness = -1 (the worst possible; the fitness otherwise is in [0, ~1.1]). The check is done on the logged threat kind and hum level of each episode.

## Training set (HOLDOUT never used)
noop 0, 7, 15, 19, 29, 37 x sigma 0 and 0.05 = 12 episodes per candidate; noise seeds 301-306 (sigma 0, unused) and 307-312 (sigma 0.05); stuck limit 150 frames, max 3000 frames. HOLDOUT (noop 3, 11, 25, 33, 41 x sigma 0 / 0.05, the `episodes4.HOLDOUT` seeds) is only used once at the end.

## Search
CMA-ES (`cma` 4.5.0) on the unit cube of the 6 genes (bounds [0, 1], start mapped in, sigma0 0.2), population 12, up to 30 generations, stop early if the best-ever has not improved for 8 generations (improvement > 1e-9), CMA seed 1. Episodes run in parallel on 14 worker processes (16 cores).
**Timing:** one full episode (start genome, noop 0, sigma 0, 760 frames, dies at x 1220) takes 2.9 s of compute (3.8 ms per frame; a 2000-frame flag run would be ~8 s). A generation is 144 episodes over 14 workers: at most ~1.4 min even if every episode were a full flag run (typically less: most candidates die earlier); 30 generations projected at **<= ~0.7 h** (measured per generation below). Far under the 8 h limit, so the full population 12 / 30 generations are used.
Per generation logged (`runs/E1_progress.json`, `E1_gen<NN>_best.{csv,npz,json}`): best / mean fitness, the best genome, the number rejected, and the best genome's noop 0 sigma 0 run (CSV + rates npz) for rendering. `runs/E1_genes.png`: each gene over the generations. Final best rendered with the R3 layout: `clips/E1_best_full.mp4`.

## The test (no retuning after seeing HOLDOUT)
- The best-ever candidate runs HOLDOUT (10 episodes) ONCE. Reported against arm A (9/10 flags, mean max_x 2958) and arm C (0/10, 1220), per episode: flag, max_x, death x + cause, ? blocks hit, mushroom, score.
- If the evolved fly is worse on HOLDOUT than arm A, that is reported as is.
- Controls (after the main run): 2 shuffled 881-neuron brains (`W_steer_jo_orn_shuf0_rn.npy`, `..._shuf1_rn.npy`), same config, bounds, floors (the real brain's), fitness, safety, budget and CMA seed; best fitness and a HOLDOUT run each, the same way.
- The 1-2 test comes later, after the 1-2 perception work.
