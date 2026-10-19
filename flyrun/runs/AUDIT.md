# flyrun audit (read-only), 2026-10-19

Scope: `flyrun/` at commit `3966d56` (working tree has no modified tracked files under `flyrun/`; 106 untracked files, all outputs: `*.npz`, `*_cma_state.pkl`, logs, one `.tmp`). Nothing was changed except this file. Every number below is either re-run by me (section 1), queried from the connectome files (section 3), or read from the cited `file:line`. Where I did not verify something I say so.

Ratings: **BLOCKER** = breaks the rebase, the tool design, or a headline claim. **SHOULD FIX** = wrong or fragile, fix before building on it. **NOTE** = record it.

## 0. The short version

1. **BLOCKER. A clean checkout cannot run anything.** All brain matrices live in gitignored `tutorials/_cache/`; `load_brain()` raises `FileNotFoundError` on `W_steer.npy` (verified on a `git archive HEAD`). No single command rebuilds them (§1.2).
2. **BLOCKER (for the claim, not for the game). The headline wiring claim has no valid control.** E1s (10/10) and E2 have no shuffle arm at all. The E1 shuffles and four of five Part-6b shuffles never walk, so they test "does it walk", not "does the wiring matter". The only valid non-connectome control (theta rule) scores 8/10 vs the real fly's 9/10 on the same HOLDOUT (§3.3).
3. **BLOCKER (for generalisation claims). HOLDOUT is not held out.** One level, one fixed list of 10 episodes (5 start offsets x sigma {0, 0.05}), used by S3d, S3e, C1, E1, E1b, AV1, E1s, the E1s ablation and E2. The perception rules were changed after looking at its deaths (§3.5).
4. **BLOCKER (tool). Entity, level and mechanism knowledge is hard-coded in 6 to 10 places each**, and there is no entity registry, mechanism plugin or output plugin (§4, §5).
5. **SHOULD FIX (claim wording). "311 looming neurons fire" is half true:** the stimulus is injected into `LC4_R`/`LPLC2_R` only, 146 of 311 (55 + 91). The left-hemisphere detectors and `LC10a_L` are never driven (§3.2).
6. **SHOULD FIX. "Nothing is trained" is printed on the title card (`render/panels.py:311`), in `fly_mario/README.md:6` and in `CLAUDE.md:6`**, but E1, E1s and E2 CMA-ES-evolve 6, 8 and 16 genes, including every cue gain, on 1-1 (§3.1).
7. **SHOULD FIX. The provenance registry is mis-tagged.** Gains frozen as "fixed" were later evolved; four knobs tagged "evolved" are dead code in v2; there is no machine-readable "fly" tag, so teal/orange is only a hand-picked list of 12 knobs, all orange, in the renderer (§3.1).
8. **SHOULD FIX. The 150-frame "stuck" rule is still in place** and ends an episode during a long no-op wait (found in E2, documented, never fixed); `stuck_frames=150` appears in 20 files (§2.3, §5).

Re-run results (§1.1): S3e, E1, E1s, Q2 and AV1-scene reproduce exactly (outcomes and trajectory hashes). M2b reproduces except for two extra arms that come from a separate command. Q2/M2b/AV1 were run in a scratch copy so tracked files were not overwritten.

---

## 1. Reproducibility

### 1.1 Headline results, re-run

| Result | Recorded | How I re-ran it | Re-run | Verdict |
|---|---|---|---|---|
| S3e HOLDOUT, real fly | 9/10 flags (`runs/S3e.md`, `S3e_holdout.json`) | own driver = the `_ep` loop of `s3_eval.py` (default knobs, v2/v2, `W_steer.npy`, 10 HOLDOUT episodes). I did **not** run `python -m flyrun.s3_eval S3e` because it overwrites tracked `S3e_holdout_*.csv/json`. | 9/10 flags; flag, max_x and trajectory md5 of all 10 episodes identical to `S3e_holdout.json` | reproduces |
| E1 HOLDOUT | 8/10 (`E1_holdout.json`) | genome from `E1_progress.json`, loop copied from `e1_evolve.main_holdout` (the command itself exits "HOLDOUT already run, once only" because the guard is `Path.exists()`) | 8/10; 10/10 (flag, max_x, traj hash) identical | reproduces; **no replay command exists for E1** (SHOULD FIX) |
| E1s HOLDOUT | 10/10 (`E1s_holdout.json`) | `e1s_evolve.holdout_episodes(values, REAL)` | 10/10; 10/10 identical | reproduces |
| Q2 (hum, 3/3 blocks) | `Q2.md`, `Q2_arms.json` | `python -m flyrun.q2_run` in `git archive HEAD` + copied `_cache` | `Q2_arms.json`, `Q2_run.csv`, `Q2_window336.csv` identical (modulo CRLF) | reproduces |
| M2b | `M2b_arms.json` | `python -m flyrun.m2b_run` (scratch) | 13 arms equal to 1e-9. `B1_near32`/`B2_near32` are not produced: they come from `python -m flyrun.m2b_run near` (`m2b_run.py:126-136, 182`), which reads and rewrites the same JSON | reproduces; hidden second command (NOTE) |
| AV1 scene (1-2, replay to x 780, both on) | `AV1.md`: max_x 885, died "enemy dx -10" at x 811, 656 frames, back-up 74 frames / 2 presses | `AV1_TAKEOVER=780 python -m flyrun.av1_run scene TAG W_steer_jo_orn_sour.npy 1 1 8.0587` (scratch) | identical result JSON apart from `tag`; 656-frame trace identical except `mdn` in **5 rows, last digit (1e-5)** | reproduces; tiny float nondeterminism (NOTE, see §1.4) |
| M2b / AV1 gains, E1s floors | `E1s_floors.json` | not re-run (needs 4 bisections, each many episodes) | - | not verified |

The AV1 scene is **assisted**: the first 509 frames replay buttons from `runs/L2_A_0_0.0.csv` (`av1_run.py:22-34`), installed by monkey-patching `scripted.Driver` at run time (`av1_run.py:147`). It is disclosed in `AV1.md`; for the tool it should be a scene definition, not a patch.

### 1.2 Brain files and what they depend on

| File (all in gitignored `tutorials/_cache/`) | Built by | Needs | Rebuild command |
|---|---|---|---|
| `steer_edges.parquet`, `steer_bodies.parquet`, `W_steer.npy` | `tutorials/20_steering.ipynb` cells 4-6 (+ `home_bodies.parquet` from nb 19, which needs the escape cast of the earlier notebooks) | `../data/malecns_v1.0` (1 GB, streamed 152M-row weights) | a notebook chain, **no command** |
| `W_steer_jo.npy`, `steer_jo_bodies.parquet`, `*_shuf{0-4}_rn.npy` | `python -m flyrun.q1_brain` | `o0_sim.build`, which imports the **legacy `brain.builder`** from `fly_mario/brain` and `../data/derived/brain_edges_N5.npz` (`o0_sim.py:14-31`) | yes, but needs legacy code + data |
| `W_steer_jo_orn.npy`, `steer_jo_orn_bodies.parquet`, shuffles | `python -m flyrun.m2_brain` | same | yes, same dependencies |
| `W_steer_jo_orn_sour.npy`, `steer_jo_orn_sour_bodies.parquet` | `python -m flyrun.av1_brain` (asserts the 881 rebuild equals the stored file) | same | yes; **no shuffled variant exists for the 907 brain** |
| `W_steer_shuf{0-4}_rn.npy` | `python -m flyrun.shuffle` (asserts `build_W(counts)` equals `W_steer.npy`) | `steer_edges.parquet` | yes |

- **BLOCKER.** The rebase to "flyrun + tutorials" must carry: the notebook chain 02 -> 19 -> 20, `o0_sim.py` plus the part of `brain.builder` it imports, and `data/derived/brain_edges_N5.npz` (a derived file, not in this repo).
- **SHOULD FIX.** Integrity checks are inconsistent. Only `part7.py` and `configs/part7.yaml` pin `sha256(W_steer.npy)`; no hash is stored for the 881 or 907 brains that every later headline uses. `shuffle.load_counts` and `av1_brain` assert internal consistency, which is a rebuild check, not a provenance check.
- **SHOULD FIX.** Inputs hidden in `runs/`: the genome chain is read from tracked result files, not config. `e1s_genome.py:22` reads `runs/E1_progress.json`; `e2_genome.py:77` reads `runs/E1s_progress.json`; `e1s_evolve.py:78` reads `runs/E1s_floors.json`; `c1_run.py:24` reads `runs/O0_qblocks.csv`; `av1_run.py:27` reads `runs/L2_A_0_0.0.csv`. `runs/` is both an output folder and a config folder. The `start: from: E1_best` key in `drives.yaml` is ignored (only `start.extra` is read, `e1s_genome.py:23`).
- **NOTE.** `README.md` documents only the interpreter (system Python 3.12.6, `requirements.txt` pins). It does not mention `tutorials/_cache`, the data, or the build order. `requirements.txt` omits `Pillow` and `scipy` (used by `render/` and `o0_*`; Pillow arrives through matplotlib, scipy does not).
- **Clean-checkout test run** (git archive + copied cache; the two slowest benchmark tests deselected): see §2.1.

### 1.3 Evolution artifacts

- Per-generation `*_gen<NN>_best.npz` (rate traces), `*_cma_state.pkl`, `E1s_*.log` are untracked or ignored, and the README says the npz are local. The CSV/JSON (`E1_progress.json`, `*_holdout.json`, `*_gen<NN>_best.json`) are tracked, so every number is regenerable from a genome; the videos and rate traces are not archived. Consistent with the repo's "video is ephemeral" rule. (NOTE)
- `evo/`, `evo4/` (Part 4), `evo5-7` contain tracked `state.pkl` and CSVs for parts that predate v2 senses; they cannot be reproduced after v2 (`SENSES_VERSION="v1"` is the only thing that still runs them). (NOTE; DROP)

### 1.4 Seeds, noise order, regression rule

- Episode seeds are explicit: TRAIN12 seeds `301 + i + 6j` (`e1_evolve.py:26`, `e1s_evolve.py:26`, `e2_evolve.py:26`), HOLDOUT `100 + i + 1` (`episodes4.py:11`); disjoint lists (start offsets 0,7,15,19,29,37 vs 3,11,25,33,41). CMA seed 1, sigma0 0.2 are hard-coded (`e1s_evolve.py:25,104`). A test of disjointness exists only for the Part-7 lists (`test_part7a.py`).
- **NOTE. Half of HOLDOUT is noise-free.** For sigma = 0 the seed is never drawn from, so 5 of the 10 episodes differ only by the start offset. "10 distinct trajectories" (E1s) is mostly start timing.
- **SHOULD FIX. The noise draw order depends on scene state.** `SensesV2.from_threat` draws 2 values per frame (`senses_v2.py:295-300`), but the sour draw happens only while an enemy is in range (`:249-253`) and the smell draw only while a mushroom is on screen (`:267-273`). Switching a drive on or off, or an enemy appearing, shifts every later draw. The SPEC's regression rule acknowledges "changes the noise draw order" but not that it is state-dependent. Consequence: "frame-identical" can only be claimed with identical toggles and scene.
- **NOTE. Float nondeterminism observed:** in the AV1 re-run 5 `mdn` values differ at 1e-5 between two runs of the same code (sparse matvec summation order / thread count). Outcomes did not change, but a threshold at 0.10 can flip a frame in a marginal run; the "identical trajectory hash" regression checks therefore hold only while no run is within float noise of a threshold.
- **Regression rule consistency (SHOULD FIX).** `SPEC.md` defines two rules ("brain change: same flags and causes, not frame-identical"; "senses code change with brain fixed: frame-identical"). The E2 prereg, AV1 and E1s use the strict one (10/10 trajectory hashes) and C1 used the loose one. Both are written down, but the choice of rule is made per sprint by the author; nothing enforces it.

---

## 2. Correctness

### 2.1 Tests

Full run in the working tree: **107 passed, 1 warning, 0 skipped, 0 xfail, 3 min 50 s** (`python -m pytest flyrun/tests`, system Python 3.12.6).

| Slow (call time) | |
|---|---|
| `test_part3::test_sigma_ladder` | 63 s, records numbers, **asserts nothing** |
| `test_part3::test_timing` | 34 s, a benchmark with up to 12 workers, **asserts nothing** |
| `test_part3::test_baseline_ranking` | 21 s |
| `test_part7d::test_run_restart_logs_resumes_and_flags_infeasible` | 19 s |
| `test_part7a::test_r3_replay_reproduces_part6b_holdout` | 15 s |

- **Report-only tests (no assertion on the numbers):** `test_flyrun::test_parity` ("Report only"), `test_part2::test_pit_ab` ("Report only"), `test_part3::test_sigma_ladder`, `test_part3::test_timing`. Together ~110 s of the suite verifies that the code runs.
- **Tests with a single weak assertion** (existence, `is not None`, counts): `test_part2::test_level_decode`, `test_death_map`, `test_part3::test_combine_ab`, `test_level_complete`, and several one-assert senses tests. Strong regression tests exist and are good: `test_part7a::test_holdout_equals_part6b`, `test_r3_replay_reproduces_part6b_holdout`, `test_senses_v2::test_default_is_v1_and_v1_reproduces_7e_logged_max_x`, `test_av1` regression tests.
- **No test covers:** `motor.decide`'s MDN branch with an airborne Mario; E1/E1s/E2 genome building (`e1s_genome.knobs_for`, `e2_genome.build`); `episodes4.HOLDOUT` contents; the 150-frame stuck rule; `render/` (no test imports it); the `FLYRUN_LEVEL` dispatch end-to-end.
- **Most tests guard parts that will be dropped** (Part 2-7: `test_part2..7e`, ~40 tests). In the rebase they should be dropped with their code or reduced to the two or three golden replays above.
- Tests depend on untracked files: `conftest.brain` loads `W_steer.npy`; `test_av1` has `skipif(not W_steer_jo_orn_sour.npy exists)`; `test_av1.py:49` and `test_l2b.py:82` `pytest.skip` when a fixture file is missing.
- Clean-checkout result (git archive HEAD + copied `_cache`, benchmark tests deselected): **105 passed, 2 deselected, 0 skipped, 1 m 59 s** with the brain cache present. Without the cache `load_brain()` raises `FileNotFoundError: W_steer.npy` (verified on the bare archive); every test using the `brain` fixture depends on it (not run in that state). So the suite is green on a clean checkout only after `tutorials/_cache` is restored by hand.

### 2.2 RAM addresses

| Address | Meaning | Used at | Verified where |
|---|---|---|---|
| `0x006D`/`0x0086` | Mario page / x | `env.py:17`, `level.py:20`, 8 more scripts | standard; consistent with gym `x_pos` in every run. **Defined twice** (env, level) |
| `0x000F`/`0x0016`/`0x006E`/`0x0087` | enemy active / type / page / x, slots 0-4 | `env.py:18-19`, `senses_v2.py:218-220` | type bytes 0x06 Goomba, 0x00 green Koopa "identified empirically on 1-1" (`S1_senses_v2.md`); 0x03 red Koopa, 0x0D piranha added on 1-2 (`L2b`) |
| `0x001E` | enemy state | `senses_v2.py:19-20` | Goomba 0/1/4/0x22 verified (`S1`); **Koopa shell states 2/3 NOT verified** (`S1_senses_v2.md:10`, `knobs.py:73`); red-Koopa shell and piranha states untested |
| `0x00CE` | Mario feet y | `senses_v2.py:18`, `run.py:122` | verified (ground 176, ledge 112) |
| `0x00CF` | enemy y; feet = y - 8 | `senses_v2.py:19`, `knobs.py:88` | measured (ground 184 vs 176) |
| `0x001D` | airborne flag (0 = on ground) | **12 files, literal `0x001D`** incl. `run.py:62,85,92,118`, `senses_v2.py:228-236`, `scripted.py:20` | verified in `S2_fly_held_jump.md:6` (3161 frames, 683 grounded) |
| `0x0756` | power-up state | `senses_v2.py:17` | O0 facts; box 12x24 "measured" |
| `0x071A`/`0x071C` | screen-left page / x | `level.py:21` and **12 more files as literals** | level map `001_level_map.csv`, `001_senses.md` (covers x < 2180 only) |
| `0x0500` + 208*page + 16*row + col | tile buffer | `level.py:16` | found empirically at pipe 1 (`001_senses.md:7`); `test_level_decode` |
| slot 5, type `0x2E` | power-up object | `env.py:20`, `senses_v2.py:87-93`, `c1_run.py:47` | O0 (`O0_facts.md:94`) |
| `0x075E`, `0x075A`, `0x079F`, `0x074E`, `0x00B5`, `0x009F`, `0x000E`, `0x0200-0x02FF` | coins, lives, star timer, area, viewport row, y-speed, state, OAM | diagnostics and scene scripts only | not behaviour inputs |

Unverified or fragile (**SHOULD FIX**): shell states; only slots 0-4 are read (`env.py:20`) and any enemy type not in `ENEMY_TYPES` (two entries on 1-1, four on 1-2) is silently invisible (`enemy_boxes` skips unknown types, `senses_v2.py:104`); I did not check other SMB enemy types, but any not in `ENEMY_TYPES` are ignored by design; "ground under the block" for hum reach is the hard-coded floor row, not the real support under the block (`senses_v2.py:79`, `level.ROW_GROUND`).

### 2.3 Known open issues

| Issue | Status | Evidence | Rating |
|---|---|---|---|
| Pipe 4 takes two jumps | **open, no fix since S3b**: jump 1 takes off ~70 px out, apex 68 px up at 30 px from the face, arrives falling; jump 2 from the foot lands on top. Reads 64 px via the `RIM_TILES {16,17}` special case | `S3b.md`, `S3c.md`, `S3e.md:17` ("pipe 4 unchanged (2 jumps)"), `level.py:24` | NOTE (flags are reached anyway) |
| Trigger-angle top end 97.6 deg | **open, "not investigated"**: S3e remeasured the A-onset angle range 40.0-97.6 deg (S3d: 50.4); the median 43.6 deg is the theta-rule control threshold | `S3e.md:24`, `C1.md:34` | SHOULD FIX (the control's threshold comes from this) |
| Shuffles that do not walk | **open**: Part 5/6b shuf 0-3 stand at x 40 and press Left; shuf4 "INVALID" (A down 96 % in silence); E1c0/E1c1 never walk (E1c0 stays at x 40, E1c1 stuck at 636) | `S3_robustness.md:55`, `007_fixes.md:27`, `E1.md:59-65` | **BLOCKER** for the control claim |
| MDN not gated in the air | **open**: `motor.py:85-90` sets Left / releases Right whenever mean MDN > 0.10, airborne or not; AV1: back-up fires "in 8-10 frame bursts on the way over a Goomba or Koopa, most of them airborne" | `AV1.md:65` | SHOULD FIX (also a design question: invariant 8 says the code must not decide, so a gate has to be a sensory input, not an `if`) |
| Read-only sour brain | **by design**: edges from the 26 new neurons onto old ones are dropped (`DNpe023` alone had 322 syn on DNa02, 171 on DNp09, 9 on the GF). 907-brain row sums fall to 0.757 min (verified); the 881 rows are unchanged | `av1_brain.py`, `AV1.md:6` | NOTE: the sour circuit is a partial circuit; label it |
| "Enemies only ahead" (eye and sour) | **open**: loom (`senses_v2.py:199`) and sour (`:135`) both ignore anything not at or ahead of his left edge. Sweet smell does see behind him (`:274`). AV1 deaths include "enemy behind, dx -10" | `AV1.md:40`, `senses_v2.py` | SHOULD FIX (design) |
| 150-frame stuck rule vs long no-ops | **open**: `run.py:28` default `stuck_frames=150`; the counter runs from frame 0, so a no-op start >= 151 ends the episode before the fly acts (15 of 20 pre-registered E2 "harder" timings, max_x 40). Also ends legitimate long back-ups | `E2_prereg.md` amendment, `E2.md` §4 | SHOULD FIX |

### 2.4 Other correctness findings

- **SHOULD FIX. `HOLDOUT once` is enforced by file existence** (`e1_evolve.py:142`, `e1s_evolve.py:166`, `e2_evolve.py:169,185,207`) and by a git-dirty check in Part 7. Deleting the JSON re-opens it; running with a different `tag` bypasses it. The ablation uses its own path (`E1s_ablation_holdout.json`), labelled "NOT the official result".
- **NOTE. Dead code:** `o0_ram.py:88` (`... if False else 0`); `senses.py` (v1) and `Muscle`/`A_HOLD`/`COOLDOWN` only matter to Part 1-7 and `ThetaRule`; `Knobs.PIT_GAIN` is "ignored in v2" (`knobs.py:91`; the knob is `knobs.py:32`).
- **NOTE. `theta_of` clamps d to >= 1 px** (`senses.py:17`), so theta saturates near 170 deg at contact. Known (S1).
- **NOTE. Process-global state:** `_ENV` is created once per process (`run.py:18-25`), but `FLYRUN_LEVEL` is read again on each `enemy_types()`/`level._lv()` call. Setting the variable after the first emulator use silently mixes 1-1 emulator with 1-2 tables. `FLYRUN_WFILE`/`FLYRUN_BODIES` are also read from `os.environ` (`brain.py:38-41`). (SHOULD FIX in the tool: pass a level/brain object.)
- **NOTE. Left-side `LC4_L`, `LPLC2_L`, `LC10a_L` masks are required (`brain.py:13-19`) but never driven** (§3.2).

---

## 3. Honesty and labelling

### 3.1 Knobs: fly (teal) vs invented (orange)

- `knobs.py` has **34 `Knobs` fields + 16 module constants/tables (plus the `INVENTED` dict); the `INVENTED` dict has 53 rows (42 "fixed", 11 "evolved")**. Every `Knobs` field is registered (`test_every_invented_knob_is_registered`). There is **no category for "from the fly"**: the registry is invented-only, so "teal" exists only as text in the renderer.
- **SHOULD FIX. Mis-tagged "fixed" but evolved:** `HUM_GAIN`, `SMELL_GAIN`, `SOUR_GAIN`, `MDN_THRESH`, `RELEASE_THRESH` (E1/E1s genes, bounds in `configs/*.yaml`); `STEER_THRESH` (E1 gene); `G`, `ALPHA`, `CLIP`, `DNP09_THRESH` (E2 genes). The registry still says "FROZEN" for the three gains, while the evolved values are 15.25 / 401.5 / 4.91 (`E1s_progress.json`), not the defaults in `Knobs` (14.53 / 213.9 / 0.0). `Knobs()` is therefore not "the fly"; the fly is `Knobs` + a JSON in `runs/`.
- **SHOULD FIX. Tagged "evolved" but dead in v2:** `A_HOLD`, `COOLDOWN`, `PIT_GAIN`, `THETA_RULE_DEG` (the last only for the control).
- **SHOULD FIX. Invented scalars outside the registry:** `HEADROOM_CLEARANCE = 2` (`senses_v2.py:126`), `ROW_GROUND`/`ROW_STAND`/`TILE`/`BUF` (`level.py:15-19`, registry covers only "tile IDs / rows"), the `8`/`16` offsets and sizes in the smell geometry (`senses_v2.py:269-278`), `stuck_frames=150`/`max_frames=3000` (`run.py:28`), `3161` (3 files), `WORST = -1`, POP/GENS/PATIENCE/CMA sigma0 (`e1s_evolve.py:24-26,104`), the 28/22/30 px triggers of the scripted player (`scripted.py:24-26`), `TOPN = 20` (`l2c_sim.py:24`), the "top-40 intermediates" in the W_steer construction.
- **SHOULD FIX. The renderer's provenance panel is not derived from the registry.** `render/panels.py:316-323` hard-codes 12 knobs, tags all of them orange, and draws "from the fly" as a static caption (`:312-315`); it omits `SOUR_GAIN`, `MDN_THRESH`, `RELEASE_THRESH`, the headroom rule, the geometry genes. It reads `c1_run.KN` (the Part-C1 defaults, not the run's genome unless the log carries overrides, `panels.py:52`).
- **SHOULD FIX. "Nothing is trained" is false for the flyrun track after E1.** E1 (6 genes), E1s (8), E2 (16) are CMA-ES on 12 training episodes of 1-1 (fitness = max_x/3161 + score/10000). `render/panels.py:311` prints "nothing is trained" on every title card (and `fly_mario/README.md:6`, `CLAUDE.md:6` say it). Accurate: "the wiring is real; 8 gains and thresholds were fitted by CMA-ES on 12 episodes of this level".
- **NOTE. Selection pressure is partly on score, not survival:** E1s best-ever is generation 8 (11/12 training flags, fitness 1.1707) over generations with 12/12 flags (1.06-1.10), because fitness adds `score/10000` (`e1s_evolve.py:53`). Coins, blocks and mushrooms are rewarded.

### 3.2 "Real wiring" claims: what the connectome says

Queried by me from `../data/derived/brain_edges_N5.npz` (every connection of >= 5 synapses between annotated bodies) joined to the annotation feather; script in the audit scratchpad. Model counts from `load_brain()` on the actual `.npy`/`.parquet`.

| Claim | Exact content | Proof file | Status |
|---|---|---|---|
| Looming -> GF | edge table: 126 LC4 + 185 LPLC2 = **311** neurons (same as the model); **302** have a direct >= 5-syn edge to `DNp01` (126 LC4: 6,362 syn; 176 LPLC2: 4,836 syn; total 11,198 syn). GF `DNp01` n = 2. `DNp01 -> TTMn`: 2 edges, 90 syn. In the model `TTMn` has one input (`DNp01`, weight 1.0 after row-normalisation). | `o0_graph.py`, `escape_circuit.py`, `tutorials/_cache/steer_edges.parquet` | real; **9 LPLC2 have no direct edge >= 5** |
| ... but driven | Model has LC4 71L+55R, LPLC2 94L+91R (311). Input is injected into **`LC4_R` and `LPLC2_R` only (146 of 311)** (`senses_v2.py:295-301`, `senses.py:81`); `LC10a_R` (140) only for home (`:302`); `*_L` never. | `brain.py:13-19` | **SHOULD FIX wording**; also contradicts the symmetric lateral wiring invariant if both GFs are meant to be driven |
| JO -> GF | 20 JO neurons (13 `JO-B1_a`: 541 syn, 6 `JO-B1_c`: 138 syn, 1 `JO-CA1`: 10 syn) = **689 synapses** onto `DNp01`; 672 JO neurons are in the edge table. Q1 adds exactly those 20 to `W_steer`. | `O0_facts.md:14-25`; my query reproduces 20 / 689 | real, direct. Hum loudness is invented (`HUM_GAIN`). |
| ORN -> DNa | **0 direct edges** (>= 5 syn) from any ORN to `DNa01/02`. The model uses 163 attractive ORNs + 62 intermediates (881 total), a 3-hop k/N extraction with predicted-NT signs. | `O0_facts.md:52-60`, `m2_brain.py`, my query (0 direct) | real as a multi-hop route; sign and weight are rule-derived, not synapse counts |
| LC10a -> DNa (home) | **0 direct** edges; routes via top-40 intermediates chosen in nb 20; the home drive itself (`HOME_R` into 140 `LC10a_R`) is invented ("the direction of travel is ours", `knobs.py:100`) | `tutorials/20_steering.ipynb` | real route; the cue is invented |
| DC4 -> MDN | **0 direct** edges. the edge table has 23 `ORN_DC4`; the model has **13 (4 L, 9 R)**, 9 intermediates, 4 MDN. The sour level is injected per neuron into both sides equally (`senses_v2.py:254`), so the right antenna carries 2.25x the neurons. MDN also receives old-network inputs (e.g. `AOTU019` -0.213) | `l2c_graph.py`, `l2c_sim.py`, `av1_brain.py`, `L2c.md`, `AV1.md` | real as a multi-hop route; read-only (new -> old edges dropped); **L/R asymmetric by selection** |

General: the model matrix is row-normalised by **in-network** input (`W = counts / row_sum * sign`, `shuffle.py:build_W`), so a weight is a share of the extracted subnetwork's input, not of the neuron's true input. `O0_facts.md:33` shows adding 854 neurons dilutes every row until looming no longer triggers. Weights across brains (636 vs 881 vs 907) are therefore not comparable. (NOTE; needs a one-paragraph disclosure in the tool.)

### 3.3 Controls: valid vs not valid

| Control | What it is | Valid? |
|---|---|---|
| Part-5 shuffle | shuffled already-normalised W | **withdrawn** by `006_audit.md` (row sums 0.006-3.55) |
| Part-6b row-renormalised degree shuffle, 5 seeds | same degree sequence and signs, rows renormalised | design valid; **result degenerate**: shuf 0-3 never walk (x 40), shuf 4 "INVALID" (free-running A). Not a test of the jump circuit |
| E1c0/E1c1 (evolved shuffled 881 brains) | same budget rule | design valid; **both never walk**, `E1.md` itself says it "does not isolate the drives". E1c1 ran 27 generations vs E1's 15 |
| theta rule (43.6 deg, no brain) | same senses, motor, knobs | valid and informative: **real 9/10 vs theta-rule 8/10** (S3e); the 43.6 deg threshold was measured from the real fly's own onsets on the same HOLDOUT |
| blind timer, spam, right-only | no-brain baselines | valid as floors |
| E1s, E2 | **no shuffle arm, no matched non-connectome evolved controller** | **missing** (CLAUDE.md allows leaving out the degree shuffle for routine runs, but not the class shuffle; no class shuffle exists in `flyrun/`) |
| 907-brain shuffles | | **do not exist** |

So the strongest claim the data supports today: "the connectome circuit, with fitted gains, plays 1-1 to the flag on the 10 HOLDOUT episodes". "The wiring is doing something" is not supported past +1 episode over the theta rule (S3e) and no evidence exists for E1s/E2.

### 3.4 Pre-registrations

- Exist for: 7a (`008_preregistration.md`, amendments 1-4 with dates), E1, E1s, E2. Each was committed before its results (git log order: `5a3bcc5`, `051c45f`, `572a18d`, `3f9f456`).
- **Amendments:** 1 (7b), 2 (7d), 3 (7e) are labelled "before" the stage they affect. **Amendment 4 (after 7e's HOLDOUT 0/10) replaced fallback rule (e)(a)** by fix 1; the text says so and the decision is the author's. E2's amendment ("after the search and after seeing the pre-registered test; logged BEFORE the extra set is run") was added in the results commit `a4b8fce` (+3 lines). All are disclosed; none hidden. (NOTE)
- **E2's harder-set defect is documented** in the amendment and `E2.md` §4 (15 of 20 timings are harness artifacts). It is **not fixed in code** (§2.3), so the next experiment inherits it. (SHOULD FIX)

### 3.5 HOLDOUT contamination

The same `episodes4.HOLDOUT` (`episodes4.py:11-13`) is the evaluation set of: Part 6b, 7e, S3d, S3e, C1, E1, E1b ("reused for explanation only"), AV1, E1s, the E1s ablation, E2 (+ a "harder" set). The S-series perception rules were changed **in response to HOLDOUT deaths** (S3d real 0/10 -> S3e fix 9/10: "G2 invisible mid-jump"). Pit 3 anchoring (S3d) was a response to a pit-3 death. The level is always 1-1 and 1-2 gives 0 flags in 12 runs (`L2.md`). HOLDOUT is a regression set on one level, not held-out data, and "unseen level" has never been tested. (BLOCKER for any generalisation wording; the rule in CLAUDE.md that shadow data "diagnoses, never scores" is respected, but HOLDOUT deaths have diagnosed and then driven rule changes.)

---

## 4. Structure (input for the tool design)

### 4.1 Layers and dependencies

```
data (../data) -> tutorials nb 02/19/20 -> tutorials/_cache (W_steer, steer_*.parquet)
   -> q1_brain (+JO) -> m2_brain (+ORN) -> av1_brain (+DC4/MDN)      [use o0_sim.build + legacy brain.builder]
env.py (gym, RAM) -> level.py (tiles) -> knobs.py (all scalars, tables)
   -> senses.py (v1) / senses_v2.py (v2: choose + SensesV2.look) -> brain.step -> motor.decide
   -> run.run_episode (the one loop; scripted.py optional prefix) -> fitness / baselines
episodes4 (TRAIN/HOLDOUT) + e*_genome (+configs/*.yaml) + e*_evolve -> runs/*_progress.json -> next genome
render/* (log.py reruns the episode; panels draw) <- c1_run (Probe, KN, ARMS)
```

Most imported: `brain` (40 importers), `run` (34), `knobs` (26), `env` (22), `level` (18), `episodes4` (17), `c1_run` (16, mostly because it holds `Probe`, `KN`, `ARMS`, `QBLOCKS` that nothing else owns).

### 4.2 Where each concept lives, and how tangled

| Concept | Where today | Tangle |
|---|---|---|
| **Enemies** | type bytes + sizes + level variants `knobs.py:74-91`; live states `senses_v2.py:20`; piranha special-case `senses_v2.py:108-120`; slot count/powerup id `env.py:20`; v1 ground-truth `env.nearest_threat_d`/`threats_ahead` (`env.py:34-60`) still used by `run.py:58-59,76` and `cause_of`; probe literals `c1_run.py:47`; facts in `l2b_enemies.py` | **HIGH**: 5 files, no table; a new enemy touches `knobs`, `senses_v2`, `run.cause_of`, `render` |
| **Pipes, steps, pits** | tile id sets + per-level dicts `level.py:23-44`; face merge and pit base/tower geometry inside `senses_v2.choose` (`:171-198`), with E2 geometry params; pipe-4 rim hack | **HIGH**: level tile ids and the invented pit-tower shape are in one function |
| **"?" blocks, mushroom, bricks** | `level.QBLOCK_TILES` (`level.py:25`), `scan_blocks` (`:129`), `senses_v2.hum_block` (`:72`), `mushroom()` (`:87`), scoring list `c1_run.QBLOCKS` from a CSV | MED |
| **Mechanisms (looming, home, hum, sweet, sour, headroom)** | all five injected in **one function**, `SensesV2.look` (`senses_v2.py:224-281`): threat choice, release/cleared state, headroom scaling, noise, then hum/smell/sour vectors, each addressing `self.m["JO"]`, `["ORN_L"]`, `["DC4_L"]`... and `assert`ing the brain variant; masks defined by cell-type strings in `brain.load_brain` (`brain.py:12-59`); toggles = `Knobs` bools; `drives.yaml` lists drives/toggles/gains but not neuron groups | **HIGH**: `choose` + `look` do selection, geometry, state, noise and five cues |
| **Outputs** | `motor.decide` (`motor.py:62-101`): TTMn -> A (hold logic in `Muscle2`), DNp09/DNa -> Right/Left, MDN -> Left; thresholds in `Knobs`; the 5-combo action list `env.py:13`; "A without direction is dropped" `motor.py:95` | **MED-HIGH**: `motor.decide` names `MDN`, `DNp09`, `DNa_R`, `SOUR_SENSE` directly; adding a button means editing `decide`, `env.COMBOS`, `run.py:101-123` columns |
| **Scenes** | one script per scene (`o0_ram.py`, `m2_run`, `m2b_run`, `q1_run`, `q2_run`, `av1_run`, `l2*`), each with literal take-over x (500/560/780/1226/1700), RAM pokes for "enemies removed" repeated 4x (`o0_ram.py:41`, `m2_run.py:58`, `q1_run.py:37`, `q2_run.py:64`), a `Sim` class in `o0_ram`, a runtime patch of `scripted.Driver` | **HIGH**: scene = code, not data |
| **Runs** | `run.run_episode` (`run.py:28-154`, ~125 lines): scene driver + no-op wait + senses + step + motor + logging + blind metric + stuck rule + summary; process-global `_ENV` | **HIGH** |
| **Evolution** | `e1_/e1s_/e2_evolve.py` are near-copies (e1 vs e1s differ in 56 diff lines; e1s vs e2 in 459 but the same skeleton, same `TRAIN12`, `POP`, `NPROC=14`, fitness, 3161); genome built from `drives.yaml` + `genome_e2.yaml`; start values read from previous `runs/*_progress.json` | **MED-HIGH** |
| **Rendering** | `render/` is clean as a package but hard-codes the neuron group table, colours, layout, font path, knob list (§5) and imports `c1_run` for the run definition | **MED** |

### 4.3 `configs/drives.yaml`: what it controls today

Read by `e1s_genome.py` / `e2_genome.py` only. **Used:** `drives.<name>.enabled`, `.gain` (name of the gain gene), `.toggles` (-> `Knobs` bool kwargs, `enemy_input` -> run argument), `perception.*.toggles`, `motor.genes`, `bounds.*`, `start.extra`.
**Ignored (decorative):** `attaches:` (never read by any code; grep), `start.from`, and in `genome_e2.yaml` `base`, `start_from`, `fixed`.
**Still hard-coded:** the brain file (`WFILE`/`BODIES` constants in 6 modules); which neuron groups a drive injects into (`senses_v2.py`); the cue geometry; the output mapping; the start genome's source file; the floor measurements (their search ranges are literals in `e1s_floors.py:27`); `part7.yaml` (a different, older schema) and `drives_e1.yaml` (a frozen copy kept because the E1 modules read it).

---

## 5. Hard-coding scan

All items cite `file:line`. "Breaks" says what fails when a new entity, mechanism or level is added.

### 5.1 Magic numbers in logic

| # | Item | Where | Breaks | Should live in |
|---|---|---|---|---|
| 1 | 150-frame stuck rule, `max_frames=3000`; `stuck_frames=150` is repeated in 20 files | `run.py:28`; `fitness.py:34`, `e1s_evolve.py:45,144`, `e2_evolve.py:45,144`, `e1_evolve.py:45`, `av1_run.py:88`, `c1_run.py:66`, ... | long no-op waits, slow levels, back-up behaviour end runs wrongly (E2 harder-set) | run/episode config (`stuck_policy`, per level) |
| 2 | 68 px apex (`MAX_JUMP_HEIGHT`), `HUM_REACH = 64`, `HEADROOM_CLEARANCE = 2` | `knobs.py:89,90`, `senses_v2.py:126`; `level.headroom` default cap `level.py:57` | jump physics differ for big Mario / other movement; HUM_REACH exists as a constant and as an evolved knob (`HUM_REACH_PX`) | measured-facts file (`facts.yaml`) |
| 3 | Mario box 12x16 / 12x24, feet offset 8, eye = top-front corner | `knobs.py:86-88`, `senses_v2.py:75,269` | other form (fire, crouch) | facts file |
| 4 | Smell geometry: mushroom 16x16, centre `+8`, antenna side rule `mxm + 8 < mx + box[0]/2` | `senses_v2.py:269-278` | other pickups (star, flower) | entity registry |
| 5 | Scripted-player triggers 28 / 22 / 30 px, hold 28 | `scripted.py:24-26`, `knobs.py:68` | assisted scenes only | scene config |
| 6 | `cause_of` tolerances: `abs(dx) <= 20`, `px -12 .. +12`, `face.x - x <= 20` | `run.py:161,163,169` | cause labels are diagnostics, but `E2`/`E1s` reports quote them | diagnostics config |
| 7 | Blind-press metric 60 px, penalty 50, flag bonus 10000 | `knobs.py:62-64` | fitness weights not in an evolution config | evolution config |
| 8 | Scene take-over x: 560, 780, 1226, 1700, 500; "enemies removed" every frame | `m2_run.py:31`, `o0_motor.py:136`, `e1s_floors.py:18`, `o0_ram.py:234,286`, `m2b_run.py:29` | every scene is level-1-1 specific | scene config |
| 9 | Flag x 3161 as the fitness normaliser (3 copies) | `e1_evolve.py:53`, `e1s_evolve.py:53`, `e2_evolve.py:53` | different level length | level facts |
| 10 | CMA pop 12, generations 30/40, patience 8/10, seed 1, sigma0 0.2, `NPROC = 14` (machine-specific), `WORST = -1` | `e1s_evolve.py:24-26,104`, `e2_evolve.py:25` | any other machine / budget | evolution config |
| 11 | Theta saturation floor `max(d, 1.0)` | `senses.py:17` | contact behaviour | facts / mechanism config |
| 12 | `Pool(6)`, `WorkerPool(12)` | `c1_run.py:135`, `av1_run.py:135`, `controls.py:70`, ... | - | run config |

### 5.2 Level-specific values

| Item | Where | Breaks | Should live in |
|---|---|---|---|
| Tile ids per level (`SOLID_WALL {18-21, 97}`, `RIM_TILES {16,17}`, `QBLOCK_TILES {192,193}`, `EXTRA_WALL/EXTRA_SOLID/CEILING_EXTRA` dicts keyed `"1-1"`/`"1-2"`) | `level.py:23-44` | every new level edits code; "1-1" entries are the unchanged defaults, 1-2 values are partially emulator-tested | level definition files (`levels/1-1.yaml`) |
| Ground rows 11-12, stand row 10, floor y 176 | `level.py:18-19`, `senses_v2.py:79,189` | levels with raised floors or underwater | level facts |
| Enemy type bytes per level | `knobs.py:75-84` (`ENEMY_TYPES_BY_LEVEL`, `enemy_types()` reads `os.environ`) | any new enemy or level; mixes env var with tables | entity registry |
| Level selection through `FLYRUN_LEVEL` env var, read at import/call time in 5 places | `env.py:26`, `level.py:39`, `knobs.py:84`, `av1_run.py:87,142`, `e1s_clips.py:12`, `e2_clips.py:12`, `e1s_log.py:18` | process-global, order-sensitive (§2.4) | explicit `Level` object |
| 1-1 specific probe/scene facts: `Probe12` vs `Probe`, `O0_qblocks.csv` positions, pit-3 anchors | `av1_run.py:58,87`, `c1_run.py:24` | - | scene config / level facts |
| Special cases: pipe-4 rim hack, 1-2 exit pipe 31 "passes sideways", 1-2 `EXTRA_WALL` removed in a diagnostic script (`l2b_structures.py:46`) | `level.py:24,26-33`, `l2b_structures.py:46` | any level with a similar structure | level definition |

### 5.3 Entity knowledge

There is **not one table**. `SIZE_TABLE`, `ENEMY_TYPES`, `ENEMY_TYPES_BY_LEVEL` (knobs), `LIVE_STATES` (`senses_v2.py:20`), `SOUR_KINDS` (`:125`), the kind list `("goomba","koopa","shell","piranha")` in `look` (`:239`), the piranha clipping branch (`:108-120`), `POWERUP_ID`/`N_ENEMY_SLOTS` (`env.py:20`), and the stomped/defeated states (comments in `senses_v2.py:20`, `S1_senses_v2.md:9`) are separate. The v1 ground truth in `env.nearest_threat_d` treats every non-0x2E active slot as an enemy (a different definition from v2's known-type filter). **BLOCKER (tool):** a new entity needs 4-6 edits. Target: one `entities.yaml` (type byte, name, size, live states, defeated states, threat/sour/smell roles, level variants).

### 5.4 Mechanism wiring

Neuron type names are written inline in: `brain.py:13-19,51-59` (all masks), `senses_v2.py:254,260,279,295-302` (`DC4_L/R`, `JO`, `ORN_L/R`, `LC4_R`, `LPLC2_R`, `LC10a_R`), `motor.py:71-87` (`TTMn`, `DNp09`, `DNa_R/L`, `MDN`), `render/panels.py:36-40,138-139` (group table + masks), `make_clips.py:29-32`, `e1s_clips.py:87-89`, `av1_gain.py:35-36,61`, `controls*.py`. That is **four independent copies of the neuron-group table** (brain, panels, make_clips, e1s_clips). Adding a mechanism (e.g. a new sense) needs: a `Knobs` bool + gain, a mask in `brain.py`, a branch in `SensesV2.look`, an assert on the brain variant, a motor branch if it has an output, a render group, a `drives.yaml` entry, and the brain build. Target: one `mechanisms/<name>.py` declaring {cell-type query, side rule, input rule, readout}, from which masks, drives.yaml-style config, the renderer group and the genome gene are derived.

### 5.5 Output mapping

`motor.decide`: TTMn mean -> A with `Muscle2` hold/landing-reset logic (`motor.py:33-59`), `DNp09` mean >= `DNP09_THRESH` -> Right, `|DNa_R - DNa_L| > STEER_THRESH` -> Left/Right, MDN > `MDN_THRESH` -> Left and Right released (`:85-90`), "a held A with no direction is dropped" (`:95`), 5-button list (`env.py:13`, no B, no Down). Run columns `a`, `right`, `left` are fixed in `run.py:115-123`. Target: output plugins (`outputs/jump.py`, `walk.py`, `steer.py`, `backup.py`) each reading a readout and returning button intents, plus one combiner.

### 5.6 Evolution setup

Gene lists: built from `drives.yaml` (`e1s_genome.py`), `genome_e2.yaml` (`e2_genome.py`, 4 extra "orange" geometry genes with literal ranges), plus the legacy `genome.py:FLY/THETA/SPAM` tuples. Bounds `0.25..4.0` / `±50 %` are in yaml; gain **floors** are results of separate scripts with literal search ranges (`e1s_floors.py:27`). TRAIN12 and HOLDOUT lists, fitness weights, safety rule ("any grounded A onset with nothing in view -> reject", `e1s_evolve.py:46-48,57`), the two stop rules, the CMA parameters and the 3161 normaliser are in code, copied across three scripts. Start genome = previous stage's `best` (`e1s_genome.py:22`, `e2_genome.py:77`). Target: one `evolution.yaml` (episodes, fitness terms, constraints, optimiser, stage chain) and one `evolve.py` driver.

### 5.7 Rendering

`render/panels.py`: canvas `W,H`, panel widths, colours (`:17-24`), **`C:/Windows/Fonts/DejaVuSans.ttf` (`:25`, Windows-only)**, group table `GROUPS`/`AV1_GROUPS` (`:36-39`, with the drive that lights each row), the 12-knob title card (`:316-323`), the "nothing is trained" caption (`:311`), `OTHER` colour. `render/montage.py`/`progress.py` hard-code "dies at x 1220", "generation 6" (`montage.py:116`, `progress.py:2`). Group colours are duplicated in `make_clips.py:29`. Target: a theme file + mechanism/entity definitions supply groups, colours, labels.

### 5.8 Paths and platform

- `render/panels.py:25` absolute Windows font path. `README.md` quotes `C:\Users\arunr\...\Python312`.
- `brain.py:9` and 30+ modules locate `tutorials/_cache` by `Path(__file__).parent.parent`; `o0_graph.py:13-23`, `o0_sim.py:14-31` reach `../data` and `fly_mario/brain` via `parents[2]`/`sys.path.insert`; `render/log.py:19`, `render/sensory.py` read the raw data (152M-row stream) and cache under `tutorials/_cache`. The rebase to "flyrun + tutorials" breaks every one of these `parents[...]` assumptions.
- `part7.py:136-146` uses `sys.executable -m pip freeze`; `e1s_floors.py:19` shells out to `python -m flyrun.av1_run` with `cwd=ROOT.parent` and `PYTHONPATH`.
- `multiprocessing` always `spawn` (Windows-compatible); `NPROC=14` is this machine.
- `.gitattributes` scoped to `flyrun/` for LF; the repo-wide `.gitignore` drops `*.mp4`, `tutorials/_cache/`.

### 5.9 Duplicated constants

| Value | Copies |
|---|---|
| `BODIES`/`WFILE` file names | `c1_run.py:21`, `e1_evolve.py:22-23`, `e1_floors.py:14`, `e1s_genome.py:13`, `m2_run.py:20`, `av1_run.py:18`, `q1_run.py:25`, `q2_run.py:50` |
| Screen-left RAM `0x071A/0x071C` | `level.py:21` + 12 more files as literals |
| `0x001D` airborne | 12 files as a literal |
| `ADDR_MARIO_PAGE/X` | `env.py:17` and `level.py:20` (identical today) |
| `TRAIN12`, POP/GENS, NPROC, 3161 | `e1_`, `e1s_`, `e2_evolve.py` (identical except GENS 30 vs 40, PATIENCE 8 vs 10, which is a silent difference) |
| Neuron-group table | `brain.py`, `render/panels.py`, `make_clips.py`, `e1s_clips.py` |
| Knob defaults vs evolved values | `knobs.py` (14.53 / 213.9 / 0.0) vs `runs/E1s_progress.json` (15.25 / 401.5 / 4.91): the "current fly" is not defined in one place |
| `drives_e1.yaml` vs `drives.yaml` | near-identical copies (E1's frozen) |

---

## 6. Keep / drop / refactor per file (for the rebase)

"Keep" = survives into the flyrun-only repo as is. "Refactor" = survives, with the change named. "Drop" = leave in git history (tag it) and do not carry. Tests follow their code.

**Core runtime**

| File | Decision |
|---|---|
| `env.py` | **Refactor**: take level and action list as arguments; one RAM address table (`ram.py`/facts), no env vars |
| `level.py` | **Refactor**: per-level data files; remove the `FLYRUN_LEVEL` read; one place for ROW_GROUND etc. |
| `knobs.py` | **Refactor**: split into (a) `Knobs` of true parameters, (b) `facts.yaml` (sizes, box, offsets, apex), (c) entity registry; replace the `INVENTED` dict with a typed registry with `fly | invented | measured` tags and evolved/fixed status derived from the evolution config |
| `brain.py` | **Refactor**: masks from mechanism declarations; brain variant passed in, not env vars |
| `senses_v2.py` | **Refactor (largest)**: split `choose` (threat selection + geometry), release/cleared state, and one plugin per mechanism (loom, headroom, hum, sweet, sour) |
| `senses.py` (v1) | **Drop** (keep `theta_of`, `Loom` dataclass) |
| `motor.py` | **Refactor**: output plugins; drop `Muscle` v1 |
| `run.py` | **Refactor**: split loop / scene driver / logging / summary / stuck policy; remove module `_ENV`; replace `0x001D`-style literals |
| `scripted.py` | **Keep (assist module)** with its constants in scene config |
| `episodes4.py` | **Refactor** into `evolution.yaml` (TRAIN, HOLDOUT) with a recorded "used for" log for HOLDOUT |
| `fitness.py`, `baselines.py` | **Refactor**: keep `WorkerPool`/`evaluate`, theta-rule and blind-timer baselines; drop spam/right-random |
| `genome.py`, `evolve.py`, `evolve4/5/6.py`, `report4.py`, `evo_report.py`, `render_stage.py`, `montage.py`, `make_clips*.py`, `make_clipP.py`, `controls*.py`, `fair_*.py` | **Drop** (Part 4-6b) |

**Brain construction**

| File | Decision |
|---|---|
| `shuffle.py` | **Keep** (`degree_shuffle`, `build_W`, `load_counts`); add a class shuffle and a 907-brain shuffle |
| `o0_sim.py` (build helper only) | **Refactor**: extract the k/N build rule into a standalone module without the legacy `brain.builder` and `sys.path` hack |
| `q1_brain.py`, `m2_brain.py`, `av1_brain.py` | **Refactor** into one `build_brain.py <mechanisms...>` with a manifest + sha256 |
| `o0_graph.py`, `l2c_graph.py`, `l2c_sim.py`, `l2b_smell.py`, `l2c_mbon_shuffle.py` | **Keep as `facts/` scripts** (they produce the wiring evidence in §3.2) after the same path cleanup; drop scratch builds duplicated by the builder |

**Scenes / assisted**

| File | Decision |
|---|---|
| `o0_ram.py` (Sim, removal, mushroom placement) | **Refactor** into the scene engine (RAM pokes as data) |
| `m2_run.py`, `m2b_run.py`, `q1_run.py`, `q2_run.py`, `q1_calibrate.py` | **Refactor** into scene configs + one scene runner; keep their numbers as goldens |
| `av1_run.py`, `av1_gain.py`, `av1_backups.py`, `av1_clip.py` | **Refactor**: `ReplayDriver` becomes a scene prefix, `Probe12` a probe; gain calibration kept as a calibration recipe |
| `c1_run.py` | **Refactor**: split `Probe`/`analyse` (keep) from the arm runner (drop); stop `render` importing it |

**Evolution**

| File | Decision |
|---|---|
| `e1_genome.py`, `e1s_genome.py`, `e2_genome.py` | **Refactor** into one genome builder over an evolution config; keep `Gene` |
| `e1_evolve.py`, `e1s_evolve.py`, `e2_evolve.py` | **Refactor** into one driver; keep the E1/E1s/E2 configs as stage files |
| `e1_floors.py`, `e1s_floors.py` | **Refactor**: floors as declarative scene tests |
| `e1b.py`, `e1s_ablation.py`, `e1s_log.py` | **Keep logic**, fold into the driver (ablation as a sub-command) |
| `part7.py`, `search7.py`, `final7e.py`, `diagnose7b.py`, `diagnose_f1.py`, `evo/`..`evo7e/` | **Drop** (Part 7) |

**Facts / one-off diagnostics**

| File | Decision |
|---|---|
| `measure_jump.py`, `levelmap.py` | **Keep** as facts scripts (apex, level map) |
| `l2_run.py`, `l2_scan.py`, `l2b_enemies.py`, `l2b_structures.py`, `l2b_tiles.py`, `l2b_ref.py` | **Keep only as provenance for the 1-2 facts** (tile ids, enemy sizes); otherwise drop; their outputs become the level/entity files |
| `smoke_s1.py`, `smoke_s2.py`, `smoke_s3.py`, `s3_eval.py`, `s3_controls.py` | **Drop** (replaced by the new regression goldens); keep `s3_eval`'s HOLDOUT loop as the seed of the evaluator |
| `c1_report.py`, `e1s_clips.py`, `e2_clips.py`, `c1_clip.py` | **Drop**; the renderer produces clips from logs |

**Render**

| File | Decision |
|---|---|
| `render/log.py`, `video.py`, `panels.py`, `montage.py`, `progress.py`, `sensory.py` | **Refactor**: theme file, groups from mechanisms, knob panel from the registry, no Windows font path, no `c1_run` import, no "nothing is trained" |

**Docs / config / tests**

| File | Decision |
|---|---|
| `SPEC.md` | **Keep** (rewrite as the spec of record; resolves the two regression rules into one) |
| `PROGRESS.md`, `runs/*.md`, `README.md` | **Keep as history**, move to `docs/history/`; write a new README with the build order |
| `configs/drives.yaml`, `drives_e1.yaml`, `genome_e2.yaml`, `part7.yaml` | **Refactor**: one schema; remove ignored keys (`attaches`, `start.from`, `base`, `fixed`) or make them read |
| `tests/` | **Keep:** `test_senses_v2` (rewrite on plugins), `test_motor_v2`, `test_av1`, `test_q1`, `test_m2`, `test_l2b`, `test_part7a::test_holdout_equals_part6b`/`r3_replay`, `test_part6b` shuffle/rebuild tests. **Drop:** `test_part2/3/4/5/7b/7d/7e`, `test_flyrun`; convert `sigma_ladder`/`timing` to a benchmark outside the suite |
| `runs/` outputs | **Keep** the small JSON/CSV/MD; drop `evo*/state.pkl`, `*_cma_state.pkl`, the `E1_E1_gen*` per-generation CSV/JSON unless wanted as history |

---

## 7. The ten worst hard-codings to remove first

| # | Hard-coding | Where | Why it hurts | Fix |
|---|---|---|---|---|
| 1 | Brain files are untracked and have no build command or manifest; the 907 brain has no hash | `tutorials/_cache/*`, `brain.py:9`, `q1/m2/av1_brain.py` | clean checkout cannot run | `build_brain` + manifest + sha256 in config |
| 2 | Entity knowledge in 5+ places (types, sizes, states, slots, piranha branch, v1 ground truth) | `knobs.py:74-91`, `senses_v2.py:20,108-120,239`, `env.py:20,38-60`, `run.py:58,161` | new entity = 4-6 edits, silent ignore of unknown types | `entities.yaml` registry |
| 3 | Mechanism wiring: neuron names inline in `look`/`decide`/`load_brain`, 4 copies of the group table | `senses_v2.py:224-302`, `brain.py:12-59`, `motor.py:71-87`, `panels.py:36-40` | new sense/output = edits in 7 places | mechanism plugin declares masks, input, readout |
| 4 | Level data in code, selected by `FLYRUN_LEVEL` env var (tile ids, rows, enemy bytes, ceiling ids) | `level.py:18-44`, `knobs.py:75-84`, `env.py:26` | new level = code edits; mixing emulator and tables in one process | level definition files + explicit `Level` |
| 5 | `stuck_frames=150`/`max_frames=3000` (150 appears in 20 files) and the stuck semantics | `run.py:28`, 20 files | long waits/back-ups end episodes; E2 harder-set invalid | run config + start counting after hand-over |
| 6 | Evolution protocol copied three times (episode lists, POP, 3161, NPROC=14, fitness, safety rule, seeds) | `e1_/e1s_/e2_evolve.py:24-57,104` | silent divergence (GENS/PATIENCE already differ); level-specific normaliser | `evolution.yaml` + one driver |
| 7 | Scene definitions as scripts with literal take-over x and per-script "enemies removed" pokes; runtime monkey-patch of `scripted.Driver` | `m2_run.py:31,58`, `m2b_run.py:29`, `q1_run.py:37`, `q2_run.py:64`, `av1_run.py:147`, `e1s_floors.py:18` | each scene is a one-off; cannot be edited in a tool | scene config (prefix, hand-over, pokes, probes) |
| 8 | Output mapping inside `motor.decide`, MDN/back-up gated on `SOUR_SENSE` | `motor.py:62-101` | new button/output = edit `decide`, `COMBOS`, run columns | output plugins + combiner |
| 9 | Provenance is not data: invented/evolved/fly tags in comments and a stale dict; renderer hard-codes 12 knobs and the "nothing is trained" caption | `knobs.py:93-150`, `render/panels.py:305-325` | teal/orange labels can be wrong; claims on video misstate the method | typed registry with `fly | measured | invented`, evolved flag from the evolution config |
| 10 | Duplicated addresses and constants (`0x001D` in 12 files, `0x071A/1C` in 13 files, `ADDR_MARIO_*` twice, `BODIES` in 8) | see §5.9 | one fix needs N edits; values can drift | one `ram.py` table; names only |

Honourable mentions: absolute Windows font path (`render/panels.py:25`); `NPROC = 14`; the read-modify-write of `M2b_arms.json` by two commands (`m2b_run.py:126-136`); `drives.yaml` keys that no code reads.

---

## Appendix: what I ran

- `git archive HEAD flyrun` into a scratch directory (+ copied `tutorials/_cache`) for the clean-checkout load test and for Q2/M2b/AV1 (so no tracked file was overwritten).
- `python -m pytest flyrun/tests` in the working tree (107 passed, 3:50) and in the scratch copy (§2.1).
- S3e / E1 / E1s HOLDOUT replays with a scratchpad driver; no files written under `flyrun/`.
- Wiring queries against `data/derived/brain_edges_N5.npz` and the annotation feather; `load_brain()` mask counts on `W_steer.npy` and `W_steer_jo_orn_sour.npy`.
- Static scans (`grep`, `ast`) for RAM literals, magic numbers, env vars, duplicated tables, importers per module, tests with no assertions, registry coverage.
- Not done: the E1s floor bisections, E2 reproduction (a 21-minute search), the 1-2 runs other than the AV1 scene, the legacy Part 4-7 reproductions, and a check of every one of the 110 files' internal logic (I read the core modules in full; the one-off scripts by header, imports and grep).
