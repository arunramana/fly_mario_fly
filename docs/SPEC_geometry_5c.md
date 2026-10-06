# SPEC Phase 5c: stimulus-geometry corrections, one at a time

Date 2026-10-06. Source: `docs/INVESTIGATION_stimulus_geometry.md` (Phase 5b; item numbers refer to its section 1 and evidence table). Written BEFORE any run of this phase.
Rule of the sprint: apply one correction, revalidate, then the next; never bundle. Test for each change: "would we make this change if it made Mario worse?" Yes = correction. No scalar is tuned on an outcome. If a step makes Mario worse, that is the result and is reported, not repaired. No new scalars are introduced in any step.

## 1. Frozen conventions (hitbox everywhere, not sprite size)
Source: the game's collision boxes (RAM 0x04AC..0x04AF Mario, 0x04B0 + 4*slot enemies), measured in the investigation (evidence rows 1a-1d, scripts `audit/p12g_a.py`, `p12g_d.py`, `p12g_b.py`). Those measurements are cited, not re-done; they are the frozen numbers. The ROM is not disassembled here: "ROM/game collision boxes" means the engine's own box bytes read from RAM.

| Quantity | Frozen value | Source | Applied in |
|---|---|---|---|
| Enemy (Goomba) hitbox width w | 10 px (box = sprite x + 3 .. + 13) | row 1b | step 4 |
| Enemy hitbox height (Goomba) | 8 px (y 196..204) | row 1b | step 4 (enemy elevation centre) |
| Mario hitbox, small | 10 wide (drawn+3 .. +13) x 12 tall | row 1b | width/eye: step 4; height: step 3 |
| Mario hitbox, big | 12 wide (drawn+2 .. +14) x 24 tall | row 1b | width/eye: step 4; height: step 3 |
| Eye position | centre of the FRONT (right) vertical edge of Mario's hitbox: x_world + 13 (small) / + 14 (big); vertical = hitbox centre | derived from 1b | step 4 |
| Distance d | surface to surface: from the eye to the nearest hitbox face of the target. Enemy: `rec.x + 3 - (mario_x + 13)` = `d_centre - 10` small (`- 11` big). Obstacle: `col_x - (mario_x + 13)` = `Face.d_px - 13` small (`- 14` big). `max(d, 1)` clamp kept | rows 1c, 1d, 2g | step 4 |
| Obstacle face extent for theta | the run's full height, elevation of its nearest point (0 for a face overlapping Mario's body); the old `1 - elev/60` weight on the run centre is replaced | investigation 3.2 | step 3 |
| Mario body for obstacle overlap | `[feet - h, feet)` with h = 12 small / 24 big (was 16 / 32) | row 1b | step 3 |
| Pursuit azimuth | 0 (no dx -> azimuth ramp) | rows 3a-3e | step 2 |

Old sprite conventions (w = 16 for every enemy via `rec.width`, Mario 16 / 32 px tall, d from Mario's left edge, centre-to-centre for enemies) STAY IN FORCE until the step that replaces them, so each step changes ONE thing. In particular `mario_centre_y` (16 / 32) and `enemy_centre_y` (16 px sprite) are untouched in steps 2 and 3 for the enemy channel; step 3 changes the 12 / 24 height only inside `brain/obstacles.py`; step 4 changes the enemy geometry (w, d, eye, and the hitbox centres used by the enemy elevation weight, as one change because they are the same convention). Assignment of the Mario-height and enemy-centre items between steps 3 and 4 is my reading of the suggested mapping; flagged for the reviewer.

### Honesty point: the hitbox choice loses the lead
theta = 40 deg (THETA_GF_DEG) is reached, centre-to-centre equivalent, at d = 21.98 px with w = 16 (current, measured closed loop: first GF spike at d = 22, theta = 40.0, B11 seed 9300) and at d = 23.7 px with w = 10 (hitbox, = 13.74 gap + 10). The hitbox convention therefore LOSES 1.7 px of lead, about half a frame at 3.5 px/frame (closing speed 3.6 observed). The 4.6-frame figure in the investigation (row 1f) is a different quantity: the surface-vs-centre lead when the sprite edge (w = 16, d - 16 = 38 vs 22) is used at 3.5 px/frame. Choosing the 10 px hitbox (the less favourable convention) rather than the 16 px sprite (+4.6 frames) is the honest choice: the value is fixed from RAM boxes before any run and not by what helps Mario. Contact with a Goomba kills at d_centre = 9 (gap -1), measured, row 1d.

## 2. Steps, in risk order
1. **Docs wording (no behaviour, no revalidation).** Provenance of `LC10A_AZIMUTH_SPLIT`, `LC10A_GAIN`, `GOAL_CUE_SALIENCE` corrected in the registry source `brain/scalars.py` (`docs/SCALARS_BRAIN.md` regenerated, generator test kept green); comment at `brain/perception.py` (old line 71) corrected: 128 px is half the screen width (a fact), treating dx as an azimuth was an invented projection; looming reaches both hemispheres identically so the L/R split is decorative for the looming channel; the hitbox-loses-lead note added to the generated doc. CLAUDE.md invariant 5 wording is NOT edited by this sprint (protected file; the experimenter decides).
2. **Pursuit azimuth -> 0.** `brain/perception.py`: `pursuit_target` returns `azimuth_deg = PURSUIT_AZIMUTH_DEG = 0.0`; `SCREEN_HALF_PX` removed. A visible small moving object on the line of sight drives both LC10a sides equally (`azimuth_shares(0, split) = (0.5, 0.5)` for any split). Nothing else changes: salience weight, arousal, gain, target selection, `dx_px` (telemetry) are identical. Consequence stated openly: the ahead/behind sign no longer reaches the brain; "go right" now comes only from the declared home landmark (invented, counted). `LC10A_AZIMUTH_SPLIT`: DECISION: keep, mark INERT in the registry. Retiring it would edit `brain/calibration.py` (derived record, `senses_calibrate.derive_split`), the mechanism constructor and tests that pin it, while behaviour is identical either way; deleting a registered constant is a larger, riskier change than the correction warrants, and the registry says honestly that it has no effect. No new scalar (`PURSUIT_AZIMUTH_DEG` is the value 0 of a deleted ramp, a definition, not a tunable; it is not registered and not exposed as an experiment input). If a later sprint retires the split constant, that is its own change.
3. **Obstacle face as an extended object (not the 3D variant).** `brain/obstacles.py` only. Mario body 12 / 24. Not started in this part.
4. **Surface-to-surface d with the obstacle d shift** (enemy w = 10, eye at hitbox front, d - 10/11 for enemies, d - 13/14 for obstacles), revalidated once as a pair. Not started in this part.

## 3. Revalidation (all seeds fresh, held out, never used before; run by the experimenter, not by the implementer)
Arms at EVERY step: real, degree shuffle, class shuffle (both shuffle controls). Frozen motor map and thresholds untouched (`brain/calibration.json` unchanged).
| Step | Seeds / scenes |
|---|---|
| 2 | E3 5300-5319; B11 6300-6319 |
| 3 | E2a synthetic (`audit/e2a_synth.py`: pipe 1, block, stairs) + E2a 7200-7219; B11 6400-6419; the x ~ 724 stall replay |
| 4 | E1 3300-3319; E2a 7300-7319; B11 6500-6519; dose-response 6600-6619 |
Smoke check by the implementer: seed 9100 only (not an evaluation).

Report-only rules: if a step makes the GF fire earlier or later than the measured take-off window (stall doc: 8-35 px before the stall point for pipe 3; first-Goomba window of the braking report), REPORT it; thresholds, gains and conventions are not adjusted. Synthetic validation (disc parity, synthetic obstacle approaches) is the only place a value may be derived and checked; game outcomes never feed back. A worse Mario after a step is recorded as the finding.

## 4. Tests (affected only)
Step 1/2: `tests/test_phase3.py` (pursuit target azimuth now 0 for ahead and behind; registry rows), `tests/test_scalars_doc.py` (generated doc equals generator), `tests/test_baseline.py`, `tests/test_e1.py`. `tool/tests/test_brain_tool.py` only if the tool is touched (it is not).
