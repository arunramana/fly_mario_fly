# Audit: does Mario's behaviour come from the connectome, or from code we added?

Investigate-only sprint (2026-09-30). No existing code, config, test or project was modified; throwaway scripts and raw
results live in `audit/` (untracked; note `audit/` is **not** in `.gitignore`, so do not `git add .`). Evidence files:
`audit/wiring_out.txt`, `audit/raw_check.csv`, `audit/summary.txt`, `audit/invented_scalars.txt`, `audit/results_*.jsonl`.

## Executive summary — is the fly doing the work? **Partly.**

**What is solid.** The wiring is real: all 8 circuits were re-extracted from the raw 151.9 M-row MaleCNS weights by
independent code and match exactly (0 edge, weight or total-input mismatches); the weight matrices contain no hand-added
edge and no sign flip. Rewiring the connectome (degree-preserving *and* fully random, 36/36 runs) destroys the behaviour
every time, silencing LPLC2 / DNp01 / DLMn / DNp09 / the steering DNs does too, and neuron-free open-loop button patterns
never get past x = 1125 (flag is x ≈ 3156). So the circuit matters and the game is not solved by trivial mashing.

**What is not.** The two "winning" configs are single-trajectory flukes, and most of the steering toward the win is
hand-placed:
1. Neither win generalises. honest_1 #36 wins on seed 10 only (seeds 11, 12 die at 1780 / 687); learn_1 ep050 wins on its
   own training seed 50 only. learn_1's *untrained* brain already wins seed 0, and the held-out win rate is 2/10 untrained
   → 3/10 → 2/10 (no learning trend). honest #31 **cannot be reproduced** from its recorded spec (finding M5).
2. The win is knife-edge: a 1e-4 change in neural activity (silencing MBONs whose output to steering is ~0.0003 current)
   diverges the trajectory within 120 frames and the fly dies at the first Goomba; ±50 % on almost every scalar in the
   jump/speed/motor/steering chain, or swapping the left/right convention, removes the win.
3. Much of "perception" is a hand-made jump cue or privileged: tile-map currents are injected straight onto the Giant
   Fiber (`wall_ahead` off → dies at the first pipe, x ≈ 435), 22 % of the enemy-frames that drive looming are off-screen,
   60 % are behind Mario, forward walking is a constant current (`home_bias`, `walk_drive`), and A is held down 75 % of
   the time mostly because MotorDirect integrates a tonic DLMn against `a_threshold`.
4. The latches the project has fought (jump network, DNp02↔pIP1) are artefacts of gain × clip and of the spike override,
   not connectome recurrence.

## Method and caveats
Ablation harness `audit/ablate.py` (monkeypatches only inside worker processes) on `tool.core.runner.run_one`; two
configs: **H36** = honest_1's training baseline (run #36, reproduced exactly: 3156, flag, 1951 frames; seeds 10, 11, 12)
and **L50** = learn_1 with frozen `real_ep050.npy` (seeds 50, 100, 101; level 1-1). n = 3 seeds (2 for scalar sweeps),
one level; chaos means single numbers are noisy, so read patterns across conditions. Denormals were flushed at CPU level
(FTZ) for speed; verified to give the identical trajectory (same max_x and jumps) on a 900-frame run. Silencing zeroes a
population's input and output (not its inbound edges); MBON silencing zeroes KC→MBON.

## Findings

| id | area | severity | evidence | suggested fix (not applied) |
|---|---|---|---|---|
| **S1** | senses | **bug** | Non-page-aware enemy distance (`bridge/perception.py:41-47`, the default when `page_perception` is off) disagrees with the drawn position by >2 px in **1181/2718** enemy-frames of run #31's replay; page-aware is exact (0/2718). Ground truth = abs x − `ScreenLeft` (0x071A/0x071C), verified against Mario's drawn x 0x03AD (0/1895 mismatches). | Make page-aware the default and re-baseline goldens. |
| **S2** | senses | non-biological shortcut | 592/2718 (22 %) active enemies are off-screen (drawn x < −16 or ≥ 256) yet feed looming (`perception.py:50-69` reads RAM slots regardless of visibility; MB spatial/odour too: `full_policy.py:566-569`). | Gate on drawn x in [0, 256). |
| **S3** | senses | non-biological shortcut | 1630/2718 (60 %) enemy-frames are *behind* Mario; `side = "R" if d >= 0 else "L"`, `ad = max(abs(d),1)` (`perception.py:67-68`) keeps them driving the left hemisphere; this is the source of the tonic looming in the TTMn plateau. `ignore_behind` exists (off by default). | Default on; or model a rear field of view explicitly. |
| **S4** | senses | non-biological shortcut | 1529/2718 (56 %) enemy-frames are >48 px vertically from Mario; theta depends only on horizontal |d| (`perception.py:64`), so an enemy on another elevation still "looms". | Use 2-D distance / visibility. |
| **S5** | senses | invented, **load-bearing** | "ahead → right hemisphere" (`perception.py:67`) has no anatomical basis. Swapping L/R removes both wins: H36 [3156,1780,687] → [1226,701,1945]; L50 seed 50 3157 → 1422 (needed patching `profiled_enemy_thetas` too). | Verify laterality from the data (LC4_L/R → DNp01_L/R) and justify or randomise. |
| **S6** | senses | non-biological shortcut | `question_block_odor` reads ±16 tiles of tile map (`tile_ram.py:143`, `full_policy.py:567`): a block beyond the right screen edge is counted in 633/1451 frames. Mushroom/goomba odour use all enemy slots. | Restrict to on-screen or model odour plume. |
| **S7** | senses | **non-biological shortcut (jump trigger)** | `wall_ahead` injects `takeoff_gain·height·proximity` straight onto DNp01 from the tile map (`full_policy.py:528`; `gap_gain·gap_input` at `:523`). Removing `wall_ahead`: H36 434/435/434, L50 435/287/435 (dies at the first pipe). `gap_gain` ±50 % changes nothing in either win (unused). | Route through sensory neurons only (`looming_gain`), report wins with `takeoff_gain = 0`. |
| S8 | senses | OK (minor) | Gap window 8 tiles reaches ≤1 tile past the screen edge in 257/257 pit frames (Mario drawn col ≥ 8); wall window 6 tiles: 0/1895. RAM addresses 0x0086/0x006D/0x0087/0x006E/0x03B8/0x03AD consistent. MB gap/speed and `?`-cue inputs share S2/S8 (not exercised by the wins). | — |
| **W1** | wiring | OK | `audit/raw_check.csv`: jump, dnp02, takeoff, speed, steering, mdn, mushroom_body, posture: model edges = raw edges (72782, 1010, 514, 167, 17767, 2458, 998608, 4519), weight mismatches 0, total-input mismatches 0. `W == sign·w/in-subgraph input` exactly (0 mismatches, `circuit.py:153-196`); no hand-added edge/sign flip. | — |
| **W2** | wiring | invented-but-plausible | Signs only for ACh/dopamine (+), GABA/glutamate (−) (`circuit.py:42-47`); glutamate = inhibitory is an assumption. Unsigned neurons are silently dropped as sources: jump 13 bodies = 16,034 of 502,124 synapses (3.2 %), steering 4,713 (1.7 %), takeoff 137 (DLMn "unclear" motor cells). | Report/flag dropped sources per circuit; test glutamate sign sensitivity. |
| **W3** | wiring | behaviour-shaping knob labelled "measured" | In-subgraph input covers only 0.1–35 % of a neuron's real input, so gains compensate: ρ(W) at g=1: jump 0.821, dnp02 0.573, takeoff 1.000, speed 0.827, steering 0.786, mdn 0.734, MB 0.983. Defaults ρ·g: jump 1.64 (g 2.0), learn_1 2.13 (g 2.6), speed 0.993, steering 0.943, mdn 0.881. `Jump.g`, spike thresholds, `ttmn_press_threshold` are "measured" by behavioural sweeps (`params.py`). | Reclassify; choose g from a stated stability criterion (ρ·g < 1) or report the latch. |
| W4 | wiring | OK (name-based) | DAN reward/punishment = type prefix (`full_policy.py:306`): 316 PAM / 16 PPL1 / 8 PPL2 / 14 PPM; the "punish" reach is 97.3 % PPL1 (PPL2 0.8 %, PPM 2.0 %), so the PPM lumping is harmless; 40 MBONs PAM-dominated, 57 PPL-dominated. PAM = reward is a label, not checkable from the annotations. | Note in docs. |
| W5 | wiring | fabricated (documented) | KC input is a random projection (7 inputs, 3 per KC, seed 0); APL = top-5 % rule; no MBON→DNp01/02 synapses so readout is a placed bias (`frac`). Posture Down/Up roles are a hypothesis. | Keep flagged. |
| **D1** | dynamics | **artefact** | Jump-network latch (zero input after one looming pulse, `audit/latch.py`): TTMn 0 for g ≤ 2.0 (ρ·g ≤ 1.64); **50 (clip) at g ≥ 2.6**; with clip 500 → 0; removing the spike override leaves it; DNp01 refractory 5 turns it into a 4–10 cycle. A supercritical gain saturated by the clip, not connectome recurrence. | Do not run g = 2.6; or treat as a known artefact in every claim. |
| **D2** | dynamics | **artefact** | DNp02↔pIP1 latch (25 at zero input) exists only with the spike override at amplitude 50; gone with spike_amp 10, refractory 8, or a pure rate model; ρ·g = 0.687 < 1, so no linear latch. `integrator.py:68-78`. | Keep refractory; justify spike_amp. |
| D3 | dynamics | invented | Threshold crossing forces the output to `spike_amp` = clip = 50 (`integrator.py:76-78`); units ("firing rate") and clip 50 are arbitrary. | — |
| D4 | dynamics | OK / perf | 400 of 485 s of a 900-frame run were `Network.step` (denormals in the unflushed jump network); FTZ gives the identical trajectory in 4.5× less time. alpha 0.3 × 10 substeps is stable. | Flush denormals (already planned). |
| **M1** | motor | **non-biological shortcut** | Every action includes Right or Left: `action_index(self.direction, …)` (`full_policy.py:843`), direction starts `"R"` (`:360`) and the R steering team gets a constant `home_bias` (`:638`); DNp09 gets a constant `walk_drive` (`:824`). H36: direction R in 1826/1951 frames; B (DNp09) in only 2 %. Forward motion is placed, not neural. | Gate Right on neuron activity; drop constant currents or derive them from sensing. |
| **M2** | motor | behaviour decided by thresholds | A is down in **74.8 %** of H36 frames: MotorDirect integrates tonic DLMn (1.5–2.9) × `dlmn_gain` 1.0 against `a_threshold` 4.0 (drive 5–14). `a_threshold`, `decay`, `ttmn_gain`, `dlmn_gain` ±50 % each remove the win in at least one of the two configs. Open-loop controls (hold, bunny-hop patterns, 60 % random A): max x 315–1125, never the flag. | Report A-held fraction; adopt `adapt_frames`; calibrate thresholds from data. |
| M3 | motor | OK (minor) | `release_on_landing` reads RAM 0x001D (`controller_modules.py:422-425`): a mechanical reflex, not neural. 64-button space and Down/Up/Left muscles are off by default and not involved in either win. | — |
| **M4** | motor | bug (provenance) | Training `play()` (`tool/core/training.py`) calls `run_from_config` without entity profiles / character settings, while Play/batch use them: the same project behaves differently in training vs Play. | Share one run path. |
| **M5** | motor | bug (reproducibility) | **honest #31 (flag 3155) does not reproduce** from its recorded spec + save state, at its own commit d4bc762 or today (806 / 689 / 286 for seeds 0/1/2 with default profiles; 1128 with today's). `projects/honest_1/entity_profiles.json` (Goomba/Koopa `looming_salience` 2.5, POWERUP odour 3.0, QUESTION_BLOCK 2.0) was edited at 07:14 UTC, after the run (05:29) and the spec stores only `enabled: true`. Run #36 does reproduce exactly. | Snapshot the profile JSON in the run spec. |
| **L1** | learning | OK mechanism, **no demonstrated benefit** | learn_1: untrained baseline flagged (seed 0, 3156); 23/100 training episodes flagged, mean 1882; held-out test wins (of 10): −1: 2, 9: 0, 19–39: 2, 49–69: 3, 79: 2, 89: 1, 99: 2. Fresh vs ep050 weights differ chaotically (seed 50: 1221 vs 3157; held-out mixed); in an earlier harness they were identical (1406 vs 1408). Shuffled training: 0/100, mean 311. Rule itself is local and correct; reward events come from RAM events (allowed) and act only through DAN→MBON→placed `frac` biases — **no control leak found**. | Evaluate on ≥20 held-out seeds before claiming learning. |
| **C1** | causal | finding | Shuffles (degree-preserving 1-3, fully random 1-3): **36/36 runs die at x 307-311** (first Goomba) in both configs → the real wiring is necessary (but any non-GF wiring would also fail). | — |
| **C2** | causal | finding | Silencing (win → x): LPLC2 284/286, DNp01 284/285, DLMn 284/289, DNp09 286, steering 296, MBONs 297/296, MDN 419/289; LC4: H36 survives (mean 1555), L50 dies (297); DNp02: irrelevant for H36, needed for L50 (297); TTMn H36 1477 (A comes from DLMn). | — |
| **C3** | causal | finding | Modules off: `motor_direct` 284/285; `wall_ahead` 434/385; `page_perception` H36 loses the win; both refractories needed; `gap_ahead` off loses H36's win (3156 → 1128) but not L50's; `mbon_readout` off keeps H36, loses L50; `mb_spatial`, `qblock` off lose L50. | — |
| **C4** | causal | finding | ±50 % scalars (31 scalars × 2 factors): the win survives only for `takeoff.gap_gain`, `takeoff.dlmn_recruit_threshold`, `dnp02` refractory (both), `dnp02.g` (L50), `odour_gain` (H36), `mbon_readout.mdn/dlmn_frac` (L50); everything in jump/speed/motor/steering breaks it, including `noise.sigma` (the win needs one noise realisation). `speed.g` and `dnp09_speed_threshold` give identical numbers (redundant knobs). | — |
| **C5** | causal | finding | Sensitivity: silencing MBONs (output ≈ 3e-4 current in H36: `mbon_agg` 0.042 × 0.0063) changes `dna02` at 1e-4 on frame 0 and Mario's position by frame 123; death follows at the first Goomba (x 297). Noise σ=0.015 alone has the same effect (seeds 11/12). | Report win *rates*, add a perturbation test to CI. |

## Answer to the audit question
*If the win survived removing the connectome but not a module/scalar, say so.* It is the other way round for the
connectome (removing it fails 36/36) — but removing any one of ~15 modules/scalars also fails, and the wins need one
specific noise realisation. So the data show the wiring is **necessary**, not that the wiring **explains** the win; the win
is carried by a fragile interaction of real circuits with hand-placed currents (wall/gap takeoff, `home_bias`,
`walk_drive`), a tonic-DLMn-driven held A, and luck on seed.

## Prioritised fix list
1. **Reproducibility (M5, M4):** snapshot entity-profile JSON in every run spec; one shared run path for training and Play; state the seed set with every win claim.
2. **Report win *rates* (C1-C5, L1):** ≥20 held-out seeds per config, plus a 1e-4 perturbation test; stop quoting single trajectories.
3. **Remove the jump cue injected at the Giant Fiber (S7):** `wall_ahead.takeoff_gain`/`gap_gain` → zero; keep only looming through LC4/LPLC2; re-evaluate.
4. **Make forward motion neural (M1):** Right/B gated by DNp09/steering activity; delete constant `home_bias`/`walk_drive` or derive from sensing.
5. **Fix perception fidelity (S1-S4, S6):** page-aware default; drawn-x visibility gate; ignore_behind default; vertical distance; on-screen odour (re-baseline goldens).
6. **Stop using latched gains (D1, D2, W3):** g with ρ·g < 1 or call the latch out; reclassify "measured" g/threshold knobs as behaviour-shaping; justify spike_amp.
7. **Motor thresholds (M2):** adopt `adapt_frames`; report A-held fraction; calibrate `a_threshold`/`dlmn_gain` from data.
8. **Verify laterality (S5)** and the glutamate/unsigned-source assumptions (W2).
9. **Learning (L1):** demonstrate a held-out gain over the untrained brain before building on it.
10. Flush denormals in the jump circuit (D4).
