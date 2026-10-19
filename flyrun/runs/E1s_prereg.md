# E1s pre-registration: evolution Stage 1 WITH sour smell on 1-1 (written and committed BEFORE the search starts; base ec39dac = main + the merged l2b)

No rule or perception change (the one drawing change, the sour marker, is renderer-only and comes later).

## 0. Housekeeping (done before this file)
- **Main's uncommitted work.** `git status` on main listed (a) my own untracked flyrun files: the per-generation logs of the E1 search and its two shuffled-brain controls (`E1_E1_gen*_best.csv / .json`, `E1_E1c0_*`, `E1_E1c1_*`) plus their `.npz` rate files; (b) files that were already uncommitted before this session and are not part of the flyrun track: modified `.gitignore`, `brain/*.py`, `docs/SCALARS_BRAIN.md`, `render/brain_panel.py`, `tool/**`, and untracked `brain/assist/`, `brain/mode.py`, `brain/seed_*.py`, `claude_setup/`, `.agents/`, `.claude/skills/`, `docs/SPEC_assisted_*.md`, `projects/**`, `IGNORED_telemetry.csv`, `grep.exe.stackdump`, `flyrun/test_out.txt`, `flyrun/evo4/fly/state.tmp`. **I committed only (a) without the `.npz` files** (commit 7ee90d3, "flyrun: E1 per-generation logs", the CSV / json logs); I did NOT commit (b): it is the other tracks' work (brain/, tool/, docs, projects), it is large, and not mine to commit; it is still uncommitted. Say if you want it committed.
- **Merge of l2b** (1a0644d: 1-2 facts L2b / L2c, the sour -> MDN back-up, headroom looming; AV1) into main as ec39dac ("flyrun: merge l2b (toggles off)"). One conflict, in `render/panels.py` (`game_panel` got a `scale` argument on main, the dashed loom box and the sour outline on l2b): both kept. `SOUR_SENSE` and `HEADROOM_LOOM` default OFF (`SOUR_GAIN` 0.0, `MDN_THRESH` 0.10 in Knobs).
- **Checks after the merge:** the E1 best genome on 1-1 HOLDOUT (881 brain, toggles as in E1) is **identical to E1: 10/10 trajectory hashes equal, 8/10 flags, mean score 1940**; the flyrun test suite: **107 passed**.

## 1. Config and genome
`configs/drives.yaml` (E1's config is kept as `configs/drives_e1.yaml`, which the E1 modules read): drives ON: looming (Goomba, Koopa, pipe faces, pit towers), home, hum (reachable "?" blocks), sweet smell (the mushroom), **sour smell (all live enemies)**; perception ON: headroom looming (never a gene). Genome, built from the config by `flyrun/e1s_genome.py` (8 genes):
`HOME_R, HUM_GAIN, SMELL_GAIN, SOUR_GAIN, TTMN_THRESH, RELEASE_THRESH, STEER_THRESH, MDN_THRESH`. Everything else fixed. **Brain: the 907-neuron sour brain** (`W_steer_jo_orn_sour.npy`, the 881 + 13 DC4 ORNs + 9 intermediates + 4 MDN; read-only additions, the old rows are unchanged).

## 2. Bounds (E1's rules) and floors (re-measured on the 907 brain, `runs/E1s_floors.json`, `flyrun/e1s_floors.py`)
Start = the E1 best genome + SOUR_GAIN 8.0587 + MDN_THRESH 0.10. Gains: log-scale 1/4x..4x of the start, lower bound = max(1/4 x, floor); thresholds +-50%.
| gene | start | floor (how measured) | bounds used |
|---|---|---|---|
| HOME_R | 0.45356 | 0.1003 (nothing in view: Right pressed in >= 95% of frames 30-300) | [0.11339, 1.81422] (1/4 x is above the floor) |
| HUM_GAIN | 13.69127 | **13.6057** (hum alone still hits block 256 in the Q2 scene) | **[13.60565, 54.76506]** (the floor is above 1/4 x = 3.42) |
| SMELL_GAIN | 439.42395 | 6.452 (smell alone, home off, still turns him in the M2b scene A) | [109.85599, 1757.69579] |
| SOUR_GAIN | 8.0587 | **4.3305** (the AV1 Koopa scene, 1-2 replay to x 780, E1 genome, sour + headroom on, still backs up: >= 5 back-up frames) | **[4.3305, 32.2348]** (the floor is above 1/4 x = 2.01) |
| TTMN_THRESH | 0.12748 | | [0.06374, 0.19122] |
| RELEASE_THRESH | 0.09777 | | [0.04889, 0.14666] |
| STEER_THRESH | 0.01013 | | [0.00507, 0.0152] |
| MDN_THRESH | 0.10 | | [0.05, 0.15] |
The hum, smell and home floors on the 907 brain are identical to the 881 ones (the new rows are read-only).

## 3. Fitness, safety, training, budget (unchanged from E1)
- Per episode `max_x / 3161 + score / 10000`; candidate fitness = the mean over the 12 training episodes; no flag or survival bonus.
- Safety: a candidate with ANY grounded A onset with nothing in view (no chosen loom threat and no hum in the log) in any training episode is rejected (fitness -1).
- Training: noop 0, 7, 15, 19, 29, 37 x sigma 0 and 0.05 (12 episodes; noise seeds 301-306 (unused at sigma 0) and 307-312). HOLDOUT (noop 3, 11, 25, 33, 41 x sigma 0 / 0.05) is never used in training.
- CMA-ES (`cma` 4.5.0) on the unit cube of the 8 genes (bounds [0, 1], start mapped in, sigma0 0.2), population 12, <= 30 generations, stop after 8 generations without improvement of the best-ever (> 1e-9), CMA seed 1, 14 worker processes.
- **Timing:** one full episode of the start genome (noop 0, sigma 0, a flag run of 2504 frames) takes **45 s** of compute (18 ms per frame on the 907 brain with headroom and sour, against 4.6 ms in E1). A generation is 144 episodes over 14 workers: **<= 7.8 min even if every episode were as long as this one; 30 generations <= 3.9 h** (typically less: many candidates die early). Under the 8 h limit, so population 12 / 30 generations are kept.

## 4. The test (no retuning after seeing HOLDOUT)
- The best-ever genome runs 1-1 HOLDOUT (10 episodes) ONCE; reported against E1 (8/10 flags, mean score 1940, mean max_x 2890) and AV1 both-on (8/10, score 3485). Per episode: flag, max_x, death x + cause, "?" blocks, mushroom, score, back-up presses (AV1: ~11 per episode) and any stalls (a run that ends "stuck").
- The 1-2 opening (noop 0, sigma 0) once, as information only (not part of the test).
- Post-hoc ablation (NOT the official result): the best genome with SOUR_GAIN at its floor and MDN_THRESH at its upper bound (back-up nearly off), on HOLDOUT, to show what the sour smell adds.
- Logs / clips after the search: per generation the best / mean fitness, the best genome and its noop 0 sigma 0 run (CSV + rates); `runs/E1s_genes.png`; `clips/E1s_best_full.mp4`, `clips/E1s_vs_E1.mp4`, `clips/E1s_backup_moments.mp4`, `clips/E1s_12_opening.mp4`. Renderer-only change: the sour marker becomes a dotted yellow box about 4 px outside the smelled enemy's red loom box, opacity proportional to the sour level, and "yellow = sour" joins the colour key.
