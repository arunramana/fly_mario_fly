# S3b: pit = base + scaled tower (senses v2 + motor v2, default knobs, no tuning, no new knobs; base eecb40a)

Spec excerpt B9 (rev 2026-10-18) is now in `flyrun/SPEC.md`. **Result: no flag. Pit 1 is crossed in one jump; pit 2 is not (falls 10 px short of the far edge). Not run on HOLDOUT, as instructed (no flag).**

## Implementation (`senses_v2.choose`)
- A pit of width W (missing floor tiles from `scan_visible`) = BASE (near edge -> far edge, 16 px deep at floor level) + TOWER (16 px wide, centred on the hole's midpoint, height min(W, MAX_JUMP_HEIGHT = 68)).
- The tower is the looming object: theta = 2 atan(h / 2d) with the 2-D gap, h measured from the take-off ground, 0 once his feet are at/above its top AND he is over it (the pipe-face rule from S2c).
- The base is not looming. It keeps "the pit is still the threat" until his left edge is past the far edge: while the tower height is 0 the pit is still the chosen threat with theta 0. A pit competes with enemies / faces by the gap to its nearest part (the base); its theta and stim_d use the tower. The S3 true-angle hole path is removed.
- Overlay (`smoke_s2.write_clip`): tower in magenta, base in orange.

## Tests (`tests/test_senses_v2.py`: 21 pass; full flyrun suite below)
- On foot, the 43.6 deg trigger (tower theta) fires this far before the near edge on each 1-1 pit (front edge to near edge), vs 0.75 W:
  | pit | W | trigger at | 0.75 W | difference |
  |---|---|---|---|---|
  | 1104 | 32 | 32 px | 24 | +8 |
  | 1376 | 48 | 44 px | 36 | +8 |
  | 2448 | 32 | 32 px | 24 | +8 |
  All within +-12 (the geometry: theta = 43.6 deg at d = 1.25 h, and the tower's left edge is W/2 - 8 px past the near edge).
- Airborne: the tower keeps its full height while he rises from the take-off ground; at the release condition (feet at/above its top AND over it) it is 0 and the pit stays THE threat (base) with theta 0 until he is past the far edge, then it is gone. Far Goombas are never chosen over it meanwhile.
- Tower height = W, capped at 68 (32, 48, 64 -> W; 80, 160 -> 68).
- Enemies and pipes unchanged (all earlier tests pass).
- Expectations changed: removed the S3 hole tests (`pit_is_the_hole...`, `hole_theta...`, `on_foot_hole_theta...`, the xfail `airborne over the gap theta stays above the trigger`); replaced by `pit_is_a_base_plus_a_tower`, `tower_height_is_W_capped...`, `on_foot_trigger_fires_within_12px...`, `airborne_the_tower_is_the_chosen_threat...`. `airborne_over_the_gap_the_pit_is_the_chosen_threat_until_past_the_far_edge` (S3) was dropped with them; the new airborne test covers it.

## 2. Pipe 4 (now read as 64 px): why two jumps (smoke, `runs/S3b_smoke_log.csv`)
| | take-off | gap to the face (front edge) | A held | release | peak | outcome |
|---|---|---|---|---|---|---|
| jump 1 (frame 486) | x 830 | 70 px | 41 frames | A still down when the loom saturates; up at frame ~527 | 68 up (feet 108, 4 px above the 64 top), apex at frame 512, x 877 | descending when he reaches the face: touches it at x 898 with feet at y 134, falls to the foot |
| jump 2 (frame 541) | x 898 | 2 px | 27 frames | still down at touch-down on the top (landing_reset not needed) | 64 up (feet exactly at the top 112) | lands on the pipe top at x 900, frame 567 |
The first jump is simply too early: the trigger at 43.6 deg on a 64 px face fires at d = 1.25 x 64 = 80 px (observed 72), and a full jump reaches its apex ~25-30 px short of the face; by the time he arrives the feet are below 112. Jump 2 starts against the face and just makes the top. Not a sense bug.

## 3. Smoke run (default knobs, v2+v2, noop 0, sigma 0, unassisted)
max_x **1414**, died in **pit 2**, 878 frames, A fraction 0.26, 2 blind presses, 0 Left presses. Pipes 1-3 one jump each; pipe 4 two (above).
| pit | W | jumps | take-off (front edge -> near edge) | 0.75 W | held | landing / outcome |
|---|---|---|---|---|---|---|
| 1 (1104) | 32 | 1 | 29 px | 24 | 24 frames, loom faded at the apex (frame 690) | landed x 1140, **crossed** |
| 2 (1376) | 48 | 1 | 42 px | 36 | 37 frames, released at frame 851 | **fell in at x 1414**, ~10 px short of the far edge (1424) |
- Pit 2: apex 68 up at frame 840; the tower height went to 0 at frame 849 (feet 117, over it) so TTMn faded and A was released at 851 with the feet at y 129. A full walking jump covers about 84 px; from 42 px out he needs ~90 (mx >= ~1412 at the far side) and lands 6-10 short. Two more details for the next decision: once he falls below the tower top (feet 129 > 128) while still over it, the tower height snaps back to 48 and theta to 175 deg (d 0) - harmless here since he is already airborne and A cannot be re-pressed. Take-off 6 px earlier than the 0.75 W figure.
- Pit 3 (2448) never reached. No HOLDOUT (needs a flag).

## Clip
`clips/S3b_run.mp4` (gitignored): the smoke run at 1x, 14.6 s, base (orange) + tower (magenta) + S2 overlay.
