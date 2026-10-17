# 008 — Part 7 pre-registration: the 1-1 win search (flyrun, assisted, disclosed)

**Amendments after this commit must be logged in this file with a date and reason, before the stage they affect runs.**

Source of truth: `flyrun/configs/part7.yaml` (sha256 `7bd5a1274d80ff2bab7b934ef8fe3c5617e25f37c16333c0c432e25cba8be467`). Arm: real `W_steer.npy` (sha256 `5c57f81f5b1d260eab6887d92a42544e35e6dfea081c4d29b125e9fba1a8e2cb`). Checked at commit `0baaf03fcb` (working tree dirty at check time: True; the 7a commit follows).

## Knobs (all INVENTED, evolved; everything else fixed from `knobs.py`)

| knob | lo | hi | int | tag |
|---|---|---|---|---|
| G | 0.2 | 1.5 | False | INVENTED (evolved) |
| TTMN_THRESH | 0.02 | 0.4 | False | INVENTED (evolved) |
| A_HOLD | 4 | 32 | True | INVENTED (evolved) |
| COOLDOWN | 0 | 30 | True | INVENTED (evolved) |
| HOME_R | 0.1 | 2.0 | False | INVENTED (evolved) |
| PIT_GAIN | 0.0 | 5.0 | False | INVENTED (evolved) |

## Conditional knob rule (applied only in 7c)

IF the 7b diagnosis finds a mistimed trigger, replace `G` as the tuned gain with `LPLC2_GAIN` [0.2, 3.0] (input gain on theta) and `LC4_GAIN` [0.2, 3.0] (input gain on |dtheta|) (both INVENTED, evolved), and fix the recurrent G at the r3 value. Otherwise the knob list stays as above. Max 2 new knobs, ever.

## CMA-ES and restarts

popsize 16, σ0 0.25, max 80 gens, early stop at 15 gens without improvement, unit-cube bounds.

| restart | kind | CMA seed | start |
|---|---|---|---|
| warm_r3 | warm | 71 | evo6/real restart 3 best, u=[0.3930940417774047, 0.7245426488116201, 0.5050935339142905, 0.07908409163526009, 0.8337085710162931, 0.2719779860536943] |
| warm_r2 | warm | 72 | evo6/real restart 2 best, u=[0.48908509398540945, 0.2112809484257167, 0.9812910142660803, 0.9381237283611376, 0.857954770950063, 0.041387424294943936] |
| fresh_97 | fresh | 73 | fresh uniform(0.05, 0.95), numpy rng 97 |
| fresh_96 | fresh | 74 | fresh uniform(0.05, 0.95), numpy rng 96 |

## Budgets

- 7d short: 15 gens per restart, restarts ['warm_r3', 'warm_r2']
- 7e full: restarts ['warm_r3', 'warm_r2', 'fresh_97', 'fresh_96'], max 80 gens each, 3 h wall-clock cap

## Episodes

TRAIN (noop × σ 0.05):

| noop_start | seed | sigma |
|---|---|---|
| 0 | 1 | 0.05 |
| 7 | 2 | 0.05 |
| 17 | 3 | 0.05 |
| 22 | 4 | 0.05 |
| 29 | 5 | 0.05 |
| 36 | 6 | 0.05 |

HOLDOUT (copied from Part 6b `episodes4.HOLDOUT`, never used in search):

| noop_start | seed | sigma |
|---|---|---|
| 3 | 101 | 0.0 |
| 11 | 102 | 0.0 |
| 25 | 103 | 0.0 |
| 33 | 104 | 0.0 |
| 41 | 105 | 0.0 |
| 3 | 101 | 0.05 |
| 11 | 102 | 0.05 |
| 25 | 103 | 0.05 |
| 33 | 104 | 0.05 |
| 41 | 105 | 0.05 |

## Fitness

`max_x + 10000·flag − 50·blind_presses` (as Part 6b; blind = A onset with no threat within 60 px), mean over episodes.

## Constraints (genome fitness = −inf if any TRAIN episode fails one)

1. **Silence:** nothing in view (no enemies, pipe/pit sense off, 600 frames, noop 0) → A_frac == 0. One run per genome.
2. **First A at a threat:** the first A onset has a stimulus distance (`stim_d`) ≤ 60 px. An episode with no A at all fails.
3. **Blind presses ≤ 8** per episode.

## WIN criterion

≥ 3/10 HOLDOUT flags AND all three constraints hold on every HOLDOUT episode.

## Amendments

### Amendment 1 — 2026-10-17 (before 7b step 2)

Four amendments, all made before any search stage ran:

- **a. Restarts.** Dropped warm r2: it fails "first A at a threat" on 10/10 HOLDOUT episodes (first A at 188 px; 7a check output below) and sits at the blind-press limit (8) on all 10. Added fresh rng 95. 7d = warm r3 + fresh rng 97 (15 gens each). 7e = warm r3 + fresh rng 97, 96, 95 (up to 80 gens each, 3 h cap). CMA seeds unchanged for the survivors (71, 73, 74) and 75 for fresh_95. The `reproduction.warm_r2` entry was removed from the yaml with the restart.
- **b. Interpreter.** Every Part 7 output is stamped with `sys.version` and a sha256 of `pip freeze`; the full freeze is `runs/008_env.txt`. `requirements.txt` is synced to the interpreter actually used (system Python 3.12.6; the repo `.venv` lacks nes_py/gym/cma/PyYAML). Noted in `flyrun/README.md`.
- **c. Line endings.** Added `flyrun/.gitattributes` (`*.yaml`, `*.json`, `*.csv` → `text eol=lf`; scoped to `flyrun/` so other tracks' files are not renormalised). Config sha256 re-verified after renormalising: worktree and committed blob agree (see the stamp on the re-run check, top of the section below).
- **d. Tests.** Tests write to a per-session tmp dir (`tests/conftest.py`), never to tracked files; `runs/002_test_numbers.json` restored from git.

The config sha256 changed because of (a); the value for the amended config is in the stamp of the re-run check (`runs/008_check.md`). Note the 7a check section further down is the *original* 7a output (kept as history, including warm r2's constraint failures); the amended-config re-run is written to `runs/008_check.md` / `008_check.json`.

**Timing caveat for the re-run:** it measured one TRAIN evaluation at 29 s wall (jobs ~15 s) versus 6 s (jobs ~3.5 s) in 7a, same code and genome, so the 7a estimates (7d ~16 min, 7e <= 2.9 h) and the re-run estimates (7d ~71 min, 7e <= 12.7 h) bracket the truth; the machine was probably loaded during the re-run. Re-time on an idle machine before 7d.

### Amendment 2 — 2026-10-17 (before 7d)

- **7b classified OTHER** (`runs/008b_diagnosis.md`). Arun's decision: no new knobs, skip 7c, run 7d. Fallback if 7d doesn't clear x≈1220: make floating block rows visible as obstacle faces (a stimulus change; requires re-running baselines).
- **7d budget rule applied.** Rule: if one TRAIN evaluation is <= 10 s wall, 7d = 15 gens per restart; if slower, 10 gens per restart. Re-timed (`--stage check`, commit 8f41622, AC power, no stray python processes, ~31% background load from other apps): one TRAIN evaluation (6 episodes + silence run) took **28.6 s wall** (jobs ~15 s each; the 7a run measured 6.2 s / 3.5 s, same code and genome, cause not found). 28.6 s > 10 s, so **7d = 10 gens per restart** (`stage_7d.gens_per_restart: 15 -> 10` in the yaml; restarts unchanged: warm_r3, fresh_97). Estimated 7d wall at this speed: ~47 min.

### Amendment 3 — 2026-10-17 (before 7e)

Arun's 7e spec, logged before any 7e search runs (yaml: restart `warm_7d` added with cma_seed 76 because seeds must be distinct and 71 belongs to `warm_r3`; the `warm_r3` entry stays for the reproduction check).

a. **7d deviation recorded.** Infeasible genomes are logged with fitness −inf. CMA-ES is told a graded value `−(−1e6 + mean_fitness)`, strictly worse than every feasible genome, so infeasible genomes still rank among themselves (`flyrun/search7.py`). Feasible-vs-infeasible ranking is identical to −inf.
b. **7e restarts** (replacing "warm r3 + fresh 97/96/95"): R1 `warm_7d` = warm from the 7d best (`evo7d/warm_r3/best_genome.json`, u in the yaml); R2 `fresh_97` = continued from its 7d CMA state (`evo7d/fresh_97/state.pkl` is copied into `evo7e/fresh_97`, generation counter continues at 10, no-improve counter reset to 0); R3 `fresh_96`; R4 `fresh_95`. CMA seeds from the yaml (76, 73, 74, 75).
c. **Budget.** 3 h wall-clock cap for the whole stage (7e time only). Generations run in 7e: R1 26, R2 22, R3 12, R4 12 (≈ 2.5 min/gen, 7d measured 2.46). Early stop per restart at 15 generations without improvement. Gens a restart does not use go to R1, then R2 (first that can still run), in a second pass after R4, inside the same cap. Actual gens run are logged.
d. **Final genome selection** (before HOLDOUT): the feasible genome with the highest TRAIN fitness across all 7e restarts (R2's pre-7e generations 0–9 count, they are the same restart). Ties → fewer blind presses. Written to `runs/008e_final_genome.json` and committed before HOLDOUT runs. No other genome is evaluated on HOLDOUT, except the labelled reference below.
e. **Fallback if no WIN.** Best feasible HOLDOUT mean max_x ≥ 2400 → (b) ship without a win (best selective run + best infeasible flag run, labelled "breaks the ≤ 8 blind-press rule"); otherwise → (a) make floating block rows visible as obstacle faces (new labelled sense), then repeat 7d → 7e. The blind-press limit is never loosened.
f. **Reference only (not a candidate):** the best INFEASIBLE genome by TRAIN mean max_x across the 7e restarts' `all_evals.csv` (with its failure reason) is run once on HOLDOUT, labelled "reference only". It cannot be the final genome.
g. **Implementation notes.** `--stage 7e` = search; `--stage 7e_select` = rule (d), writes the final genome and the reference genome; `--stage 7e_holdout` = refuses unless `008e_final_genome.json` is committed and unchanged, and refuses to run twice (HOLDOUT result file must not exist).

### Amendment 4 — 2026-10-17 (after 7e, before fix 1)

"7e's fallback (a) targeted the x≈1220 ledge, which 7e already clears 10/10. Arun's decision: fix the new main death instead (the x≈1532 two-Goomba death). This is fix 1 of 2 max." Fallback rule (e)(a) is therefore replaced by fix 1 (`runs/009_fix1.md`); constraints, fitness and the WIN criterion are unchanged. `PROGRESS.md` "What's next" updated to match.

---

## 7a check output (`python -m flyrun.part7 --config flyrun/configs/part7.yaml --stage check`)

### Part 7a check  (commit 0baaf03fcb +DIRTY, config 7bd5a1274d80, W 5c57f81f5b1d)

## 1. Config validation

| check                                     | result |
|-------------------------------------------|--------|
| yaml validates                            | PASS   |
| W sha256 matches the file                 | PASS   |
| HOLDOUT == Part 6b (episodes4.HOLDOUT)    | PASS   |
| knob ranges == Part 6b (genome.FLY)       | PASS   |
| fitness constants == knobs.py             | PASS   |
| every restart has an explicit CMA seed    | PASS   |
| warm_r3: u == evo6/real gen.csv restart 3 | PASS   |
| warm_r3: yaml decode == genome.decode     | PASS   |
| warm_r2: u == evo6/real gen.csv restart 2 | PASS   |
| warm_r2: yaml decode == genome.decode     | PASS   |

## 2. Part 6b HOLDOUT reproduction

| restart | mean_max_x | expected | flags | expected | max_x list identical | result |
|---------|------------|----------|-------|----------|----------------------|--------|
| warm_r3 | 1405.1     | 1405.1   | 1     | 1        | True                 | PASS   |
| warm_r2 | 1937.0     | 1937.0   | 0     | 0        | True                 | PASS   |

## 3. Constraints on HOLDOUT, per episode (silence is one run per genome)

**warm_r3**  genome {'G': 0.7110222543106262, 'TTMN_THRESH': 0.2953262065484157, 'A_HOLD': 18, 'COOLDOWN': 2, 'HOME_R': 1.684046284930957, 'PIT_GAIN': 1.3598899302684715}  silence A_frac = 0.000  -> all constraints on every episode: PASS

| noop | seed | sigma | max_x | end         | silence | first A at threat | blind<=8 |
|------|------|-------|-------|-------------|---------|-------------------|----------|
| 3    | 101  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 11   | 102  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 25   | 103  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 33   | 104  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 41   | 105  | 0.0   | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 3    | 101  | 0.05  | 3161  | flag        | ok      | ok (24px)         | ok (8)   |
| 11   | 102  | 0.05  | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (5)   |
| 25   | 103  | 0.05  | 1221  | enemy dx=10 | ok      | ok (26px)         | ok (6)   |
| 33   | 104  | 0.05  | 1129  | pit         | ok      | ok (26px)         | ok (6)   |
| 41   | 105  | 0.05  | 1220  | enemy dx=10 | ok      | ok (26px)         | ok (5)   |

**warm_r2**  genome {'G': 0.8358106221810324, 'TTMN_THRESH': 0.10028676040177235, 'A_HOLD': 31, 'COOLDOWN': 28, 'HOME_R': 1.7301140648051196, 'PIT_GAIN': 0.20693712147471968}  silence A_frac = 0.000  -> all constraints on every episode: FAIL

| noop | seed | sigma | max_x | end        | silence | first A at threat | blind<=8 |
|------|------|-------|-------|------------|---------|-------------------|----------|
| 3    | 101  | 0.0   | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 11   | 102  | 0.0   | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 25   | 103  | 0.0   | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 33   | 104  | 0.0   | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 41   | 105  | 0.0   | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 3    | 101  | 0.05  | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 11   | 102  | 0.05  | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 25   | 103  | 0.05  | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 33   | 104  | 0.05  | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |
| 41   | 105  | 0.05  | 1937  | enemy dx=9 | ok      | FAIL (188px)      | ok (8)   |

## 4. TRAIN timing (r3 genome, 6 TRAIN episodes + 1 silence run)

wall for one evaluation on 12 workers: 6.2s;  per-job seconds: 6.2, 3.5, 3.5, 3.5, 3.3, 3.5, 0.7
TRAIN: mean_max_x 1415, flags 0/6, all constraints ok: True

One generation = 16 genomes x 7 jobs = 386 worker-s (job speed measured with up to 12 concurrent workers). Estimates assume perfect packing:

| stage                                | generations | wall @12 workers | wall @8 workers |
|--------------------------------------|-------------|------------------|-----------------|
| 7d short                             | 30          | 16 min           | 24 min          |
| 7e full (upper bound, no early stop) | 320         | 2.9 h            | 4.3 h           |

7e cap 3 h: does not bind

**check: PASS** (constraint failures on r3/r2 are information, not check failures)
