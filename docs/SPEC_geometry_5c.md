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

## 5. Step 3 (2026-10-06): obstacle face as an extended object. Written BEFORE the code change and before any run of the step.
Test: "would we make this change if it made Mario worse?" Yes: the old rule evaluates the elevation weight at the run CENTRE, a point, for an object that is 16-64 px tall. That is a modelling artefact (investigation 3.2), not a result.

**Rule.**
1. Mario's body for the obstacle overlap is `[feet - h, feet)` with h = 12 (small) / 24 (big), the hitbox heights of section 1 (was 16 / 32). Small vs big is still read from the RAM size byte (0x0756). `feet` is the hitbox bottom byte (0x04AF), unchanged.
2. An obstacle face is the visible solid run overlapping that body, nearest column first, longest overlapping run wins (unchanged). Its width for theta is `w = 16 px * run length` (unchanged). The face now also carries its vertical extent `[top_y, bottom_y]` (screen y of the run's top and bottom edges).
3. Elevation is that of the NEAREST POINT of the face to Mario's body: the vertical gap between the interval `[top_y, bottom_y]` and the body interval `[feet - h, feet]`, zero when they overlap. Face selection (step 2 above) requires overlap, so the elevation is 0 for every face that is selected, grounded or airborne; the weight is evaluated through the general nearest-point function so it stays correct if selection changes later. Elevation angle = `atan(gap / d)`.
4. `theta = 2 atan(w / (2 d)) * max(0, 1 - elev / ELEVATION_LIMIT_DEG)`, `d` unchanged (left edge of face minus left edge of Mario, `max(d, 1)`; the surface-to-surface shift is step 4). The weight function shape and the 60 deg cap (invented `ELEVATION_LIMIT_DEG`) are unchanged. Enemies are untouched (`mario_centre_y`, `enemy_centre_y` stay). No new scalar, motor map, calibration, threshold, LC10a gain or landmark change.

**Expected effect (investigation 3.2, 3.3).** With the centre-point artefact gone the theta of a tall face is simply `2 atan(H / 2d)`, monotone in approach. The GF (theta about 40 deg) should first fire at d about 43 (pipe 1, 32 px), 63-65 (pipe 2, 48 px) and 84-87 (pipe 3, 64 px), earlier than before for the tall faces. Presses may therefore be EARLY relative to the take-off windows measured in the stall doc (pipe 1: 1-frame tap window 5-29 px before the stall point, longer holds 35-65; pipe 3: hold >= 10 needed, window 8-35 px before the stall point). 

**REPORT-ONLY rule.** If the GF fires or A is first pressed too early or too late versus those windows, that is reported. No threshold, gain, convention or window is adjusted. A worse Mario is the result.

**Validation (synthetic only).** `audit/e2a_synth.py` (pipes 1/2/3 = 32/48/64 px, a 16 px block, a 1-tile step; running 3.0 and walking 2.57 px/frame; real vs 5 degree shuffles; landmark off and on): theta trace, GF first-spike d and theta, first A press px before the stall point versus the windows; flat ground theta 0; disc 38-48 deg with the mechanism on; rest silent. Numbers are recorded in section 6 after the run. Smoke seed 9100 only. Tests: `tests/test_e2a.py` (old centre-point assertions updated, extended-object elevation test added).

## 6. Step 3 synthetic validation numbers (2026-10-06; `audit/e2a_synth.py --noise-seeds 1 --shuffles 5`, noise seed 9100, 5 degree shuffles, open loop from x 318, stall point x 434 = face 448 - 14; nothing tuned)
Bench changes (stimulus values, not scalars): walking speed 2.57 px/frame (was 1.75), Mario body 12 px, geometries pipe_48x3 / pipe_64x4 / step_16 added. Stairs first step and block_16 give the same nearest face as step_16 (identical traces).

| Face | Speed | Peak theta (d<=14) | GF first spike d / theta / px before stall (landmark off) | First A, px before stall (off / on) | Versus window |
|---|---|---|---|---|---|
| pipe 1 (32) | run 3.0 | 97.6 | 43.0 / 40.8 / 29 | 23 / 17 | inside 5-29 (GF at its far edge) |
| pipe 1 | walk 2.57 | 97.6 | 42.6 / 41.2 / 28.6 | 18.3 / 18.3 | inside |
| pipe 2 (48) | run | 119.5 | 61.0 / 43.0 / 47 | 41 / 32 | no measured window (reported only) |
| pipe 2 | walk | 119.5 | 63.2 / 41.6 / 49.2 | 44 / 41.5 | no measured window |
| pipe 3 (64) | run | 132.7 | 85.0 / 41.3 / 71 | 65 / 65 | EARLY: window 8-35, A about 30 px before its far edge |
| pipe 3 | walk | 132.7 | 81.2 / 43.0 / 67.2 | 59.5 / 46.6 | EARLY by about 25 (off) / 12 (on) px |
| 1-tile step / block (16) | run | 59.5 | 19.0 / 45.7 / 5 | 5 / 2 | at the near edge of the 1-frame window (no own window measured) |
| 1-tile step / block | walk | 59.5 | 19.5 / 44.6 / 5.5 | 2.9 / 2.9 | same |

Monotone theta for all pipes (the old inversion is gone). The GF distances are the predicted 43 / 61-63 / 81-85. Shuffled (degree), landmark off: 0 GF spikes and no A in all 5 shuffles for every geometry and speed. Real, landmark on equals landmark off for GF (the landmark shifts A by 0-13 px later in some rows). Shuffled with landmark ON: the GF fires at frame 0 (d about 129, theta of the face only 7-28 deg) in 5/5 shuffles, A in 3/5: the landmark alone drives the shuffled network; this is a property of the landmark mechanism on a rewired network, not of step 3 (stimulus at that frame is not the obstacle), reported only.
Flat ground: 3000 frames, theta != 0 in 0 frames. Disc with the mechanism attached and landmark on: first GF spike at 47.2 / 47.2 / 40.6 / 43.6 deg for l/v 10 / 20 / 40 / 80 ms (all within 38-48). Rest 1000 frames: 0 GF spikes (real, landmark off and on; shuffled 1-3).
Reported, not adjusted: the GF/A press for pipe 3 comes earlier than the 8-35 px take-off window (A 47-65 px before the stall point), as the investigation's caveat predicted; a ground press that early is a hop that lands before the pipe or too high-energy for the window, so a different failure (early press) is expected in the game, to be judged by the experimenter's seeds.

## 7. Step 4 (2026-10-06): surface-to-surface d, enemy hitbox width, obstacle d shift. Written BEFORE the code change and before any run of the step.
Test: "would we make this change if it made Mario worse?" Yes. The eye is at the front of Mario's hitbox and the target is its nearest hitbox face; these are RAM collision boxes (section 1), frozen before any run. It is a correction, not a choice by outcome. One change (enemy w, enemy d and obstacle d are one convention, applied as a pair).

**Formulas (one helper, `front_edge_offset_px(size_byte)`: 13 small (size byte 0) / 14 big).**
1. Enemy: `d_centre = enemy_x - mario_x` (page aware, unchanged; "ahead" still means `d_centre >= 0`). `d = d_centre - 10` small / `- 11` big (= `rec.x + 3 - (mario_x + 13)`, the enemy box left edge minus Mario's front edge). `w = 10` for every enemy (ENEMY_HITBOX_W_PX; the registry's 16 px is retained only for the on-screen test and the pursuit channel). `theta = 2 atan(w / (2 max(d, 1))) * max(0, 1 - elev / 60)`. Elevation weight, 60 deg cap and the sprite-based vertical centres (`mario_centre_y`, `enemy_centre_y`) are UNCHANGED (the brief for this step fixes the elevation weight; section 1 listed hitbox centres for step 4, I am NOT changing them: flagged); the elevation angle uses the same `max(d, 1)` as theta, i.e. the surface distance. For a same-level Goomba both centres are 200, elevation 0, so this does not matter on flat ground.
2. Obstacle: `Face.d_px` stays `col_x - mario_x` (the face selection `d > 0` is unchanged). The distance the fly sees is `Face.d_px - 13` small / `- 14` big (`col_x - (mario_x + 13)`), returned unclamped as the telemetry distance, `max(d, 1)` inside theta. `theta_of(..., eye_offset_px=0)` keeps the old behaviour as the default argument (documented, used only by tests); the policy path passes the front-edge offset. Face width (16 px x run) and the extended-object elevation (step 3) unchanged.
3. `brain/scenes.py check_e2a_scene` passed the old 16/32 body height to `nearest_face`; it now passes 12/24 (`BODY_SMALL_PX/BODY_BIG_PX`). `nearest_face` only reads the height to find the overlapping run, and `face_dx_px` / `face_w_px` do not depend on it for the pinned scene, so the manifest check is unchanged in value.
4. Pursuit channel, motor map, calibration, thresholds, LC10a, scalars: UNCHANGED. No new scalar (10, 13/14 are frozen RAM box numbers, section 1).

**Expected timing effects (computed from the frozen numbers, before any run).**
- Enemy: theta = 40 deg needs surface distance d = 5 / tan 20 deg = 13.74 px, i.e. `d_centre = 23.7` (small Mario), against 22.0 now. Contact kills at `d_centre = 9`, surface distance -1 (the boxes overlap by 1 px). Lead from first GF spike to contact: (13.74 - (-1)) = 14.74 px = 4.2 frames at 3.5 px/frame, 4.1 at 3.6 (walking Goomba plus Mario). Now (centre, w = 16): (22 - 9) = 13 px = 3.7 frames. So the GF fires about 0.4-0.5 frame EARLIER relative to contact, not later: the hitbox convention costs the sprite's 16-px lead (section 1 honesty point) but gains 1.7 px by referencing the true contact distance. For a standing Goomba (closing 0.6 px/frame, Mario standing) the lead is 24.6 frames. The disc calibration (theta vs time, 38-48 deg) is unchanged because the disc is a theta trace, not a RAM distance; no new calibration is run.
- Obstacle: the distance the fly sees drops by 13 px for the same position, so theta at a given Mario x is larger: the GF (theta 40 deg) fires 13 px FURTHER from the face. Pipe 3 (64 px): theta 40 deg at surface d = 32 / tan 20 deg = 87.9, i.e. `Face.d_px` 101.9; the stall point is `Face.d_px = 14` (surface d = 1), so the GF is ~88 px before the stall point (was ~71 run / ~67 walk). Pipe 1: theta 40 deg at surface d 16 / tan 20 deg = 44.0, i.e. 44 + 13 - 14 = 43 px before the stall point (was 29): the far edge of the 5-29 window is exceeded. Presses move earlier by about the same 13 px.
- Honesty note: the hitbox choice loses the 16 px sprite's lead (+4.6 frames of the investigation, row 1f); the 10 px hitbox is the less favourable, honest choice.
- REPORT-ONLY: if the GF or A is too early or late vs the take-off windows (pipe 1 5-29 px before the stall point, pipe 3 8-35, first-Goomba window of the braking report), it is reported. Thresholds, gains, caps and conventions are not changed. Game outcomes never feed back.

**Validation (synthetic only).** Goomba approach (Mario standing, enemy closing 0.6 px/frame; walking, closing 3.6 px/frame): first GF spike d, theta, frames to contact (contact at surface d = -1 i.e. `d_centre = 9`); pipes 1/2/3 run (3.0) and walk (2.57): GF d and first A versus windows; disc 38-48 deg; rest silent; flat ground theta 0; 5 degree shuffles with landmark off. Smoke seed 9100 only. Numbers are recorded in section 8.

## 8. Step 4 synthetic validation numbers (2026-10-06; smoke seed 9100; `audit/step4_goomba_synth.py`, `audit/e2a_synth.py --noise-seeds 1 --shuffles 5`; nothing tuned)
Goomba (synthetic RAM through the real `enemy_thetas`, small Mario, integer RAM positions, start d_centre 150, contact at d_centre 9 = surface distance -1):
| Case | First GF spike d_centre / surface d / theta | Frames before contact |
|---|---|---|
| standing Goomba (closing 0.6) | 23 / 13 / 42.1 deg | 24 (predicted 24.6) |
| walking Goomba (closing 3.6) | 24 / 14 / 39.3 deg | 5 (predicted 4.1; spike one frame later than the threshold crossing; rounding of the integer d_centre) |
Shuffled (degree, 5): 0/5 GF spikes in both. Old convention for comparison (w = 16, centre d, first spike d 22): 13 px = 3.7 frames at 3.5; so lead is not lost against contact, but the 16 px sprite's extra lead is not taken.

Pipes (open loop, stall point x 434 = surface d 1; running 3.0 / walking 2.57; face drawn from x 303; table from x0 = 318 unless stated). The theta trace is monotone and flat ground is 0 (3000 frames, 0 nonzero).
| Face | GF first spike surface d / theta / px before stall (run; walk) | First A px before stall (run off/on; walk off/on) | Window | Versus window |
|---|---|---|---|---|
| pipe 1 (32) | 42.0 / 41.7 / 41 ; 42.5 / 41.3 / 41.5 | 29 / 32 ; 36 / 29 | 5-29 (1-frame tap) | GF EARLY by 12 px (was 29); A at or past the far edge (29-36) |
| pipe 2 (48) | 60.0 / 43.6 / 59 ; 65.6 / 40.2 / 65 | 50 / 44 ; 54 / 60 | none measured | reported |
| pipe 3 (64), x0 = 318 | 117 / 30.6 / 116 ; 117 / 30.6 / 116 | 77 ; 77 | 8-35 | start artefact: GF at frame 0 (the face is already drawn at theta 30.6 with a first-frame dtheta of the same size); NOT a threshold crossing |
| pipe 3 (64), x0 = 303 (face enters the screen at theta 0) | 87 / 40.4 / 86 ; 83.2 / 42.1 / 82 | 80 ; 74 | 8-35 | EARLY by about 45-50 px (was 71 run) |
| 1-tile step / block (16) | 21.0 / 41.7 / 20 ; 21.9 / 40.1 / 21 | 14 ; 16-18 | none | mid-window of a 1-frame tap |
Shifts agree with the predicted 13 px (pipe 1 29 -> 41 is 12; pipe 3 71 -> 86 is 15; pipe 2 47-49 -> 59-65). Shuffled (degree), landmark off: 0 GF spikes and no A in 5/5 for every geometry and speed. Shuffled with landmark ON: the GF fires at frame 0 in 5/5 and A in 3/5 for every geometry (the landmark alone drives the shuffled network; same as step 3, reported only).
Disc with the mechanism attached, landmark on: GF first spike at 47.2 / 47.2 / 40.6 / 43.6 deg for l/v 10 / 20 / 40 / 80 ms (identical to step 3; the disc is a theta trace and is not affected). Rest 1000 frames: 0 GF spikes (real, landmark off and on; shuffled 1-3).
Reported, not adjusted: obstacle GF and A presses are earlier than the measured take-off windows (pipe 1 by ~12 px, pipe 3 by ~45-50 px). In the game the pipe-3 onset (the face appears at the screen edge) can also fire the GF on the onset transient; this is a property of the bench start x0 = 318 and of onset dtheta, to be judged by the experimenter's seeds.
