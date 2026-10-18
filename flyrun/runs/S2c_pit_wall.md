# S2c: face "above AND over" + pit virtual wall (senses v2, motor v2 as built; no tuning, no search)

Spec file `claude/flyrun-behaviour-spec.md` is not in the repo; built from the S2c message (B6 / B9 as described there).

## 0. MAX_JUMP_HEIGHT = 68 px (INVENTED, fixed, measured)
`flyrun/measure_jump.py`: 60 frames of Right on flat ground (walking speed), then Right+A held for 30 / 40 / 50 frames, ground y 176,
apex = take-off feet y - min feet y. All three give 68 (the hold saturates by 30 frames). Smoke-run jumps held 25-26 frames reach 64.

## 1. Face rule: above AND over
A face (neighbouring equal-height columns merged: a pipe is one face) keeps its full height from the take-off ground until his feet are
at/above its top AND his body (12 px box) overlaps its columns. Only then 0. A face fully behind his left edge is ignored.

## 2. Pit = virtual wall
One virtual face per pit at the near edge, top = 176 - 68, height 68, same rule with strict "feet above top" (can never happen).
Kind `pitwall`. Kept the pit-below rule (tile under his footprint -> threat at d 0, kind `pit`). The pit stops being a threat when his left
edge is at/past the far edge. The old per-tile ahead threats are gone.

## Tests (`tests/test_senses_v2.py`, 20 pass; full flyrun suite 71 pass)
Expectations changed by the spec: face_height_is_above_feet (feet-above case now also needs "over"), face_height_constant_while_rising
(feet at/above top but not over -> still H, over -> None), step_face_stays_16 (same), senses_tracks_the_take_off_ground (140 -> 32),
pit_tiles_are_individual_threats replaced by pit_is_one_virtual_wall_and_the_tile_under_him, airborne-over-gap (kind pit or pitwall),
the kinds set in the episode test (+pitwall). New: 48 px pipe above-not-over / over, two-column pipe, wall height during the rise and
over the gap, threat ends past the far edge.

## Smoke run (default knobs, v2 + v2, sigma 0, noop 0 seed 0, 1-1 from the start, UNASSISTED; `S2c_smoke_log.csv`, `S2c_jumps.csv`)
max_x 3161, end_reason **flag**, 1921 frames, A fraction 0.34, blind presses 4, Left presses 0. One episode: not a HOLDOUT result, no claim beyond it.
- Pipe 1 (448, 32): 1 jump. Pipe 2 (608, 48): 1. Pipe 3 (736, 64): 1 (take-off was for a Goomba, the face took over in the air, landed on top).
  Pipe 4 (912, 48 as read): 1 jump, lands on top (S2b: never).
- Pit 1 (1104): crossed, in 2 jumps. The first (A held 48 frames) landed at x 1092, on the edge; the landing reset (A up one frame) then re-pressed
  with the wall at d 0 (TTMn 0.41) and the second jump crossed. First run of the landing-reset path in a real episode. Pit 2 (1376): same, 2 jumps.
- Death map: none. 26 fly jumps, 19 released by loom fade, 7 still down at landing.
- Assisted pit-1 run not needed (he reaches pit 1 on his own); the S2b assisted run is not repeated.

## Found on the way (not fixed, not asked)
The level reader sees pipe 4 as 48 px. Tile column at x 912 is `[... 16, 20, 20, 20]` (rows 7-10): the rim tiles are ids 16/17, not in `SOLID_WALL`
{18..21, 97}, so the reader stops one tile short. He actually stands at feet y 112 on top (64 px). This is probably why S2b stuck at pipe 4
(feet released at the believed top, 128, 16 px below the real one). Pipes 1-3 and the stairs are read correctly.
Also the `short of the face` label on jump 4 is the table's heuristic (landed at x 900, on the pipe); it is not a miss.
