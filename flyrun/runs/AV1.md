# AV1: sour smell -> MDN -> "back up", plus headroom-scaled looming (branch l2b, base d2df1e6 + main's E1 merged; new brain variant, the default brain is untouched)

**Result.** The mechanism works on the scene it was made for: at the x ~ 890 Koopa under the floating block the headroom factor is 0, the loom is suppressed (TTMn 0.0004, no jump), the sour cue grows with the Koopa's angle, **MDN crosses 0.10 at x 874 (theta 55 deg) and he backs up (Left, 74 frames, 2 presses)**. It does not end the way the spec expected: the Koopa does follow him into the open and the loom fires again (factor back to 1), but a second Koopa was trailing him, and he **dies at x 811 to the enemy behind him (dx -10)**; max_x 885 against 890 without the new drives, and every arm still dies in this scene. **Step 5 (1-1 HOLDOUT, both toggles on) is not clean: 8/10 flags, the same as E1 (mean max_x 2930 vs 2890, 5.1 "?" blocks vs 3.6, mushroom eaten 10/10 vs 7/10, score 3485 vs 1940), but back-up fires 108 times (1932 frames, ~11 per episode, not ~0) and one of the two failures is new: stuck on open ground at x 1251 (a back-up stall at the x 1221 Goomba).** I did not merge into main.

## 1. Brain and regression (step 1)
- `python -m flyrun.av1_brain` -> `W_steer_jo_orn_sour.npy` + `steer_jo_orn_sour_bodies.parquet` (907 neurons: the 881 + 13 ORN_DC4 + 9 intermediates (M_adPNm5 x2, CL366, M_spPN5t10, CB0431, M_adPNm3, GNG519, CRE042, DNpe023) + 4 MDN); the 881 file is untouched. The rebuild of the 881 by the same rule reproduces `W_steer_jo_orn.npy` exactly (asserted).
- **The first build broke the old behaviour, so the sour branch is READ-ONLY.** `o0_sim.build` keeps every >= 5-synapse edge from a new neuron onto an old one (DNpe023 alone: 322 synapses on DNa02, 171 on DNp09, 9 on the Giant Fiber), which renormalises 29 old rows: with toggles off the E1 genome then got 7/10 and ate the mushroom 0 times (E1: 8/10, 7). Keeping only the edges onto the 4 old k/N members still moved the smell steering. Dropping every new -> old edge leaves all old rows exactly as before and MDN responds identically (steady MDN at level 20: 0.264 either way). (So L2c's V / DC4 DNp09 and steering numbers, which used the unrestricted build, included those extra edges.)
- **Regression, E1 genome, 1-1 HOLDOUT, toggles off (`runs/AV1_reg_old_holdout.json`, `AV1_reg_sour_holdout.json`):** the 881 brain with the new code is **frame-identical** to E1 (all 10 trajectory hashes equal E1's, 8/10); the 907 brain with SOUR / HEADROOM off is **also identical** (same 10 hashes: flags, the two x 1806 enemy deaths at sigma 0.05, blocks, mushrooms, score 1940).

## 2. SOUR_GAIN (step 2, frozen: `runs/AV1_sour_gain.json`)
Sour level = SOUR_GAIN x theta_enemy into every DC4 ORN, both antennae equally. Requirement: MDN (mean of the 4) = 0.10 at theta_enemy = 50 deg (just past the looming trigger, 43.6 deg), so in the open the jump fires first.
- Steady drive in the sour brain (E1 genome: HOME_R 0.4536, G 0.5, 10 substeps, 100 frames), bisection on the uniform DC4 level: **MDN = 0.1000 at level\* = 7.0326** (rest 0.0139, at level 200 0.327).
- theta\* = 50 deg = 0.87266 rad -> **SOUR_GAIN = 7.0326 / 0.87266 = 8.0587**. Check: theta 20 / 30 / 40 / 43.6 / 50 / 60 / 90 deg -> MDN 0.048 / 0.065 / 0.082 / 0.089 / 0.100 / 0.118 / 0.171.
- Dynamics (a 16 px Goomba closing from 80 px): the leak delays the crossing: MDN passes 0.10 at theta 52.8 deg at 0.9 px/frame and 61.3 deg at 1.9 px/frame (peak 0.15 / 0.17). MDN_THRESH = 0.10, fixed.

## 3. Code and tests (step 3)
`knobs.py` (SOUR_SENSE, SOUR_GAIN, MDN_THRESH, HEADROOM_LOOM + registry rows; the toggle set records `sour` / `headroom_loom` only when on), `brain.py` (DC4_L / DC4_R / MDN masks; ORN_L / ORN_R now exclude DC4), `senses_v2.py` (`sour_enemy`, `headroom_factor`, the two feeds in `look`), `motor.py` (MDN > MDN_THRESH -> Left, Right released, A untouched; `mdn` readout), `run.py` (`mdn`, `backup` columns when sour is on), `render/panels.py` (dashed red loom box when the factor < 1; thin yellow outline on the sour enemy; index rows "DC4 sour" and "MDN back up"; the 12-row index is tighter), `av1_run.py`, `av1_gain.py`, `av1_clip.py`, `av1_brain.py`, `av1_backups.py`, `tests/test_av1.py` (10 tests: factor 1 on open ground; scaling with a low ceiling; **factor 0 under the x ~ 890 pillar fixture**; MDN above threshold -> Left pressed and Right released (and Left+A); nothing when sour is off; sour picks the nearest, a shell and an enemy behind do not smell; level = gain x theta on both DC4 sides; all toggles off -> identical input; the sour brain leaves the old rows alone). Full flyrun suite: **107 passed**.
Interpretations the spec left open (all in `SPEC.md`): nearest enemy = smallest 2-D gap among enemies not behind him and not cleared; shells do not smell sour; **the headroom is measured from the take-off ground** (the first version used his current head: under any block the factor then flickered to 0 mid-jump).

## 4. The scene and 1-2 (step 4)
**The E1 genome cannot reach x 890 on its own: from the start of 1-2 it dies at x 180 (first Goomba; x 235 with sour on) in every arm.** For the scene the first 509 frames are a replay of the L2 arm A buttons (ASSISTED / diagnostic; the emulator is deterministic, and the scripted player cannot cross the 1-2 opening), then the E1 fly takes over from a silent brain at x 780, grounded, with the Koopa in view.

Scene, per frame (`runs/AV1_scene_frames.csv`, both on; x = Mario; angles in deg):
| frame | x | headroom factor (rise) | loom theta (unscaled) | sour theta | sour level | MDN | TTMn | buttons |
|---|---|---|---|---|---|---|---|---|
| 555 | 862 | 0 (0) | 0 (35.1) | 35.1 | 4.93 | 0.071 | 0.0004 | R |
| 561 | 873 | 0 (0) | 0 (55.1) | 55.1 | 7.75 | **0.099** | 0.0004 | R |
| 564 | 878 | 0 (0) | 0 (73.7) | 73.7 | 10.37 | 0.127 | 0.0004 | **L** (back-up begins at frame 562, x 874) |
| 573 | 885 | 0 (0) | 0 (161) | 161 | 22.7 | 0.288 | 0.0004 | L (his closest point, x 885; the Koopa at 898) |
| 585 | 878 | 0 (0) | 0 (170) | 170 | 24.0 | 0.314 | 0.0004 | L |
| 600 | 856 | 0 (0) | 0 (90) | 90 | 12.7 | 0.189 | 0.0004 | L |

Then he backs to x 821, turns right twice and left twice (MDN hovering around 0.10 as the Koopa, 25 px ahead and moving left, closes in), and at frame 655 the Koopa has left the block's columns: **factor 1, theta 170, TTMn 0.33, he jumps (Left + A) and the Koopa that had been trailing him at x 801 hits him from behind (dx -10) at x 811.** With a single Koopa the sequence would have been the expected one; in 1-2 there are two.

| arm (scene, takeover x 780) | max_x | death | back-up frames / presses |
|---|---|---|---|
| sour off / headroom off (= E1) | 890 | Koopa ahead (dx 10), 572 frames | 0 / 0 |
| sour on / headroom off | **1126** | enemy dx -6 (748 frames) | 47 / 4 |
| sour off / headroom on | 890 | same as E1 (loom suppressed, no jump, no back-up) | 0 / 0 |
| both on | 885 | enemy behind, dx -10 at x 811 (656 frames) | 74 / 2 |

Sour alone is the best arm (max_x 1126, score 1000): with the loom not suppressed he jumps when it fires and backs up in the gaps.

| arm (1-2 from the start, noop 0 sigma 0) | max_x | death | blocks | mushroom | back-up frames / presses |
|---|---|---|---|---|---|
| off / off | 180 | Goomba (dx 10), 94 frames | 1 | no | 0 / 0 |
| sour on / headroom off | 235 | Goomba (dx 10) | 4 | no | 71 / 2 |
| sour off / headroom on | 180 | same as off / off | 1 | no | 0 / 0 |
| both on | 235 | same as sour only | 4 | no | 71 / 2 |

Nothing gets past the 1-2 opening: the first Goomba in the low-ceiling corridor (rise 32) kills the E1 fly with or without the new drives; with sour on he backs up in mid-jump over it (MDN 0.10-0.32 when the Goomba is within ~15 px) and dies to the second one at x 235.

## 5. 1-1 check (step 5; `runs/AV1_both_on_holdout.json`, 10 HOLDOUT episodes, E1 genome, both toggles on, sour brain)
| | E1 | both on |
|---|---|---|
| flags | 8/10 | **8/10** |
| mean max_x | 2890 | 2930 |
| deaths | x 1806 enemy (x2, sigma 0.05) | x 2743 enemy (sigma 0.05), **x 1251 stuck on open ground (sigma 0.05)** |
| "?" blocks / episode | 3.6 | 5.1 |
| mushroom eaten | 7/10 | 10/10 |
| score (mean) | 1940 | 3485 |
| back-up presses (frames) | 0 | **108 (1932)**, ~11 / episode |
| Left presses | 14 | 148 |

Where back-up fires (`runs/AV1_11_backups.csv`, 3 traced episodes): not in the open, but **in 8-10 frame bursts on the way over a Goomba or Koopa** (most of them airborne), when the sour theta passes 53-90 deg (the enemy within ~8-18 px) and the jump has not yet cleared it, and in 60-85 frame stretches at x 1221 and x 1783 / 1995. The premise "the jump fires first, so back-up only wins when the loom is suppressed" does not hold: MDN is not gated by the jump, so back-up wins the last frames of every close pass. One consequence is the new failure (the 80-frame back-up at x 1221 leaves him stuck on open ground in one episode).

On the headline numbers 1-1 is not worse (same flags, higher max_x / score / blocks / mushroom), but I would not call it clean: the back-up count is far from 0 and a new failure mode appeared. **Not merged into main** (main's working tree also carries a lot of uncommitted work). The decision is yours; possible fixes, none tried and none in the spec: gate sour on being grounded, or release back-up while the jump is held.

## 6. Files
`clips/AV1_koopa_scene.mp4` (R3 layout, x 780-885 and the death, 2.6 s; red dashed = suppressed loom, yellow = the sour enemy, index rows DC4 sour / MDN back up), `clips/AV1_12_full.mp4` (1-2 from the start, both on, 4.1 s: dies at x 235), `runs/AV1_*.csv|json` (`AV1_{off_off,sour_off,off_hr,both}_12_trace.csv`, `AV1_sc_*_scene_trace.csv`, `AV1_11_both_*_trace.csv`, `AV1_scene_frames.csv`, `AV1_11_backups.csv`, the HOLDOUT jsons, `AV1_sour_gain.json`). The clips are in `flyrun/clips/` and are gitignored; the traces are the durable record.
