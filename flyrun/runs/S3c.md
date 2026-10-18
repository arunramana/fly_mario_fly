# S3c: tower moves to the far edge + flicker fix (senses v2 + motor v2, default knobs, no tuning, no new knobs; base e0a9f71)

**Result: no flag. Pits 1 and 2 are each crossed in one jump; he dies in pit 3 (x 2469) because nothing looms there. Not run on HOLDOUT (needs a flag).** No rule changed after seeing it.

## 0. Spec
`flyrun/SPEC.md` B9 updated as asked (tower on the FAR edge, 0.25 W + ~8 px expected take-off, stays released until landing; note on the S3b middle tower).

## 1. Implementation
- `senses_v2.choose`: tower x = the pit's far edge (16 px wide, near face = the hole's far edge), height min(W, 68); base unchanged; the pit competes with other threats by its base gap.
- Flicker fix: `SensesV2` remembers the pits whose tower was released while airborne; their tower stays 0 until the landing reset (the `released` set is cleared when RAM says he is grounded). S3b showed the tower snapping back to 48 / theta 175 deg when his feet fell below its top while still over it; that cannot happen now. Pipe faces are unchanged.
- Overlay unchanged (tower magenta, base orange).

## Tests (`tests/test_senses_v2.py`, 22 pass; full flyrun suite: see commit)
| pit | W | trigger fires this far before the near edge (front edge -> near edge) | 0.25 W + 8 | difference |
|---|---|---|---|---|
| 1104 | 32 | 8 px | 16 | -8 |
| 1376 | 48 | 12 px | 20 | -8 |
| 2448 | 32 | 8 px | 16 | -8 |
All within +-12. (On foot, from the ground; the geometry is theta = 43.6 deg at d = 1.25 h with the tower W px past the near edge.)
- `test_released_tower_does_not_reappear_until_landing`: rising, released (feet at the top and over it), falling below the top while still over it -> stays 0; landing -> full again.
- Enemies / pipes: unchanged, all their tests pass.
- Changed expectations: `pit_is_a_base_plus_a_tower` (tower at x 128..144 for a pit at 96, d 76, dsel 44); `on_foot_trigger_fires_within_12px...` (now 0.25 W + 8, distances 8 / 12 / 8); `airborne_the_tower_is_the_chosen_threat...` (far-edge geometry); new `released_tower_does_not_reappear...`. `tower_height_is_W_capped...` unchanged.

## 2. Smoke (default knobs, v2+v2, noop 0, sigma 0, unassisted): `runs/S3c_smoke_log.csv`, `runs/S3c_jumps.csv`, `runs/S3c_full_run.csv`
max_x **2469**, died (pit 3), 1577 frames, A fraction 0.27, 2 blind presses, 0 Left presses. Pipes 1-3 one jump each.
| pit | W | jumps | take-off (front edge -> near edge) | 0.25 W + 8 | held | landing x | outcome |
|---|---|---|---|---|---|---|---|
| 1 (1104) | 32 | 1 | 6 px | 16 | 25 frames | 1164 | crossed |
| 2 (1376) | 48 | 1 | 11 px | 20 | 37 frames | 1436 | crossed |
| 3 (2448) | 32 | 0 | - | - | - | - | **walked in: never jumped** |
(All the way to x 2424 the rest of the run is as in S2c: Goombas, Koopa, the first staircase.)

**Why pit 3 kills him (not fixed).** The pit sits between two 64 px staircase tops (stairs 2400/2416 up to feet y 112, then the pit 2448-2480, then wall 2480 at 64). He stands on the top step (feet 112, take-off ground 112). The tower is anchored to the FLOOR (176 - 32 = top 144), which is 32 px BELOW his feet, so its height from his take-off ground is 112 - 144 < 0 -> 0: the tower never exists. The next stair (2480, top 112) is level with his feet: face height 0. Net: nothing looms, TTMn 0.0004 for 40 frames, he walks off the step into the hole (frames 1544-1577). The base is still "the threat" (pit chosen on every frame, theta 0). The spec's "height above the floor" and "measured from the take-off ground" disagree when the take-off ground is not the floor; that is what failed. Options for you: anchor the tower to the take-off ground (top = ground - min(W, 68)), or add the pit's depth below his feet. I changed neither.

**Pipe 4 (read as 64 px): jumps only.** Jump 1 at frame 486 from x 830 (70 px from the face), A held 41, lands x 899 at the foot; jump 2 at frame 541 from x 898 (2 px), A held 27, lands on top x 900 (frame 567). Same as S3b (this part did not touch pipes).

## 3. Saved
- `clips/S3c_full_run.mp4` (gitignored): the whole smoke episode, 1577 frames = 26.3 s at 1x, with overlay (base orange, tower magenta, threat box, theta, TTMn, A).
- `runs/S3c_full_run.csv`: frame, x, feet_y, airborne, threat, box_x_top_w_h (the tower for pits), pit_base_x_top_w_h, theta_deg, ttmn, a, right, left.
- No HOLDOUT ran, so no `S3c_holdout_*` traces.
