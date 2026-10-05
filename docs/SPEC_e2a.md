# SPEC: E2a, obstacle expansion (one pipe)

Status: written before any code or any validation number. Decisions of Arun (2026-10-05): ALL static obstacles ahead (pipes, blocks,
steps) are perceived as retinal expansion caused by Mario's own approach, entering ONLY at the existing looming inputs (LC4 and
LPLC2 through the existing `LoomingMechanism` encoding). No new sensory population, no LC10a, no downstream current, no change to
the motor map, calibration or thresholds. Geometry comes from what is drawn: the visible tile map in RAM.

Honest label (library + tool): **"looming from static obstacles (biology: expansion cue; no source for obstacle-triggered jumps in
flies; this is a Mario's-eye-view assumption)"**. docs/INVESTIGATION_phase6.md (b) measured the route: a pipe face rendered at
LC4/LPLC2 fires the GF about 40 px before the face; there is no route from LC10a.

## 1. Encoding rule (fixed here, before validating)
Per frame, from RAM only (tile buffer 0x0500-0x069F via `mario.ram.tile_ram` read-only, screen left edge, Mario's hitbox):
1. **Visible columns.** Metatile columns whose x lies inside the drawn screen (`screen_left <= x < screen_left + 256`). Nothing
   outside the picture is seen (the "view range" is the screen width, a fact of the screen: no new scalar).
2. **Solid tile.** Any non-zero tile in the buffer. Measured on 1-1 (first 900 frames): the buffer holds only pipes (0x12-0x15),
   bricks 0x51, ground 0x54, "?" 0xC0/0xC1; scenery (hills, bushes, clouds) is not in it. Not verified beyond 1-1 (coins and hidden
   blocks of other levels are unchecked).
3. **Floor is not an obstacle.** Only tile rows 0-10 are considered; rows 11-12 are the floor. Flat ground gives theta 0.
4. **Obstacle face = a column ahead whose solid tile overlaps Mario's body.** Ahead means `d = column_left_x - mario_x > 0`
   (same left-edge-to-left-edge convention as `enemy_thetas`; contact is at d about 14 for a wall, an enemy touches at |dx| < 16).
   Mario's body extent is the screen-y interval `[feet - h, feet)` with feet = hitbox bottom (RAM 0x04AF), h = 16 small / 32 big
   (as `mario_centre_y`). Tile row r spans y `[32 + 16 r, 48 + 16 r)` (measured: the floor row 11 is at y 208). For standing small
   Mario the body overlaps row 10, so "the next step above his feet" is a tile in row 10. A Mario in the air sees the rows he is
   level with: a pipe he is above gives nothing.
5. **Nearest only.** The nearest such column (smallest d). Both hemispheres get the same value (frontal object, as enemies).
6. **Size.** The face is the contiguous vertical run of solid tiles (rows 0-10) in that column that contains the body-overlapping
   tile (the longest such run if there are two). **w = 16 px x run length**: the face extent in the picture plane perpendicular to
   the approach, the analogue of a Goomba's 16 px width (a pipe 1 face: 32, a single block or first stair step: 16). Justification:
   a wall seen from the side subtends its vertical extent; its depth is not visible; the width convention for enemies is likewise
   the sprite extent in the picture plane.
7. **theta = 2 atan(w / (2 max(d, 1)))** times the elevation weight `max(0, 1 - elev / ELEVATION_LIMIT_DEG)`, elev =
   atan(|face_centre_y - mario_centre_y| / max(d, 1)). The SAME weight function and limit (60 deg) as enemies; the face centre is
   the centre of the run (the object centre, as `enemy_centre_y`). dtheta = theta - previous theta of this mechanism.
8. **Motion is Mario's own.** d shrinks only because Mario walks (the geometry is re-read every frame); nothing adds motion.
   The stimulus is `theta` into LPLC2 and `|dtheta|` into LC4, both hemispheres, via `LoomingMechanism.encode`.
9. **Sum with enemies.** The obstacle mechanism is a separate `ObstacleExpansion(LoomingMechanism)` instance with its own theta
   trace; `Brain.apply` adds, so an enemy and an obstacle in view add at the same neurons (two objects in the field).
New scalars: **0** for the encoding. Registered (conventions of the scene/eval): `E2A_MAX_FRAMES`, `E2A_SCENE_WALK_FRAMES`,
`E2A_SCENE_SETTLE_FRAMES` (invented), `E2A_PIPE_RIGHT_X` (measured geometry).

Switched on in `SenseSettings.obstacle_expansion` (default OFF: E0/E1/E3 unchanged; their stamps are unchanged because the key
is written only when true). `settings_for(id)` turns it on when the library entry lists `expanding_obstacle`: E2a and B11.
The 1-1 baseline B11 is now defined with it ON; the earlier B11 result stays recorded as the "without obstacle expansion" baseline.

## 2. Synthetic validation plan (script `audit/e2a_synth.py`, tests `tests/test_e2a.py`); nothing tuned, failures are reported
Open loop, as docs/INVESTIGATION_phase6.md: Mario's x follows a fixed trace, the face stays at x = 448, Mario stops at 434 (the
measured stall point, 14 px before the face). Per-frame speeds measured on the emulator: **walking (right only) 1.75 px/frame**
(xspeed 28/16), **running (right + B) 3 px/frame** (xspeed 48/16).
- (i) Geometries: pipe 1 (2 tiles, 32 x 32 at x 448), a single 16 px block (1 tile in row 10), a four-column staircase (heights
  1, 2, 3, 4 tiles; first step 16 px). Per case and speed: theta trace; GF fires? at which d, theta and distance before the stall
  point; first A press frame and position. Real vs 5 degree-preserving shuffles (shuffle seeds 1-5), home landmark off and on.
- (ii) Flat ground: theta is exactly 0 on every frame over a 3000 px synthetic walk and on the real emulator over the flat start
  of 1-1 (before any obstacle is on screen); no stimulus object is produced.
- (iii) The disc (l/v 10, 20, 40, 80 ms) with `ObstacleExpansion` attached and the landmark on: GF first spike at 38-48 deg. Rest
  (no stimulus, 1000 frames) with it attached: GF silent, no latching (and equal to the run without the mechanism).
- Timing slack (real arm, pipe 1): GF spike position vs the take-off window of INVESTIGATION_phase6 (b): a 1-frame A tap clears
  pipe 1 only if pressed 5-29 px before the stall point (2 frames: 5-35; 3: 0-41; 4: 0-47).

## 3. E2a scene and metrics (fixed before any run)
Scene `brain/scenes/e2a_pipe1.json`, the E1/E3 replay-log pattern: from reset, "right" for `E2A_SCENE_WALK_FRAMES` frames, then all
buttons released for `E2A_SCENE_SETTLE_FRAMES` frames, so Mario stands still on flat ground a fixed distance before pipe 1 (checked
only that: pipe 1 face in view ahead, Mario stationary, no enemy). Rule `clear_enemies` (scene setup, disclosed; precedent E0/E3):
the first Goomba is removed so only the pipe is tested. The fly takes over with the home landmark ON (as in the baseline); looming
and obstacle expansion on; no pursuit.
Metrics (outcome-neutral):
- **cleared**: Mario's world x > 479 (`E2A_PIPE_RIGHT_X`, the pipe's right edge) while alive within `E2A_MAX_FRAMES` = 600 frames
  (invented bound, 10 s). Other ends: **died**, **stuck** (no new max x for `BASELINE_STUCK_FRAMES` = 300 frames, the existing
  window), **timeout**.
- Also recorded: GF fired before the face (first GF spike while Mario's x < 448), first-A frame / x / run length, take-off x (first
  airborne frame), tap (first A run <= `BASELINE_TAP_MAX_FRAMES` = 2), GF and TTMn peaks, max x.
Arms: real, shuffled (degree), shuffled_class, and the eval-only necessity arm `real_no_obstacle` (obstacle expansion off).
Seeds 7100-7119 (not run by the implementer); shuffle seed 1 + i. CLI `python -m brain.e2a --n 20 --seed0 7100 --workers 4 --out f.json`.
Criterion (stated before running): **real clears in >= 14/20** (REDESIGN_PLAN section 4); **degree shuffle <= 2/20**; class
shuffle informative only; the necessity arm `real_no_obstacle` is expected to fail (<= 2/20: without the cue a walker stalls at
the pipe). pipes 2-4 are not tested here (48-64 px need holds of 6-12 frames, INVESTIGATION_phase6 (b)).

## 4. Files
NEW `brain/obstacles.py` (face geometry from RAM), `brain/e2a.py` (episode, eval, CLI), `brain/scenes/e2a_pipe1.json`,
`tests/test_e2a.py`, `audit/e2a_synth.py`. ADAPTED: `brain/mechanisms.py` (+`ObstacleExpansion`), `brain/policy.py`,
`brain/settings.py`, `brain/library.py` (E2a runnable, B11 lists the mechanism), `brain/scenes.py` (id), `brain/scalars.py`,
`docs/SCALARS_BRAIN.md` (regenerated), `docs/SPEC_baseline_1-1.md` (appended section), tool dispatch (`tool/core/brain_runner.py`,
`tool/ui/brain_runs.py`, `tool/ui/tabs/results.py`). Frozen legacy untouched; motor map, calibration, manifest untouched.
