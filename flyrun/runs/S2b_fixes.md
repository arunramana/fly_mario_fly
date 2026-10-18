# S2b — face rule + pit-below (flyrun)

Both changes are inside the senses-v2 path (`senses_v2.py`); v1 senses and the v1 / S1 / S2 tests are untouched (the one S1 test whose expectation the spec changed, the pit tile at mx = 100, was updated and says so). No knob, search, or motor change. `diagnose7b.capture` now forwards `**run_kw` to `run_episode` (needed for the assisted pit run).

## What changed
1. **Face rule (B6/B8).** A face's looming height = its full height from the ground he *took off from* (`SensesV2.ground`: his current ground while grounded, the last grounded y while airborne). It stays constant while he rises and becomes 0 once his feet are above the face's top (`feet <= top`), so a step is ≈16 px relative to where he stood. `choose(..., ground=...)`; default `ground = feet` keeps the S1 behaviour on the ground.
2. **Pit-below rule (B9).** A pit tile is a candidate if it is ahead OR its right edge is still beyond his left edge (his footprint overlaps it). A tile that overlaps his footprint is directly under him: **surface gap 0** (I implemented "d ≈ 0" literally: his height above the gap is ignored for the tile under him, θ then saturates at ≈ 166°). Tiles fully behind him are dropped; ahead tiles still use the 2-D gap.

## Tests (`tests/test_senses_v2.py`, 16 now)
Rising beside a 32 and a 64 px pipe: height constant for every frame until the feet reach the top, then no face; step 2's face stays 16 until his feet clear its top; airborne over a 32 px pit the pit tile is the chosen threat on every frame from x 84 to 127 (a Goomba 150 px ahead is never chosen) and the threat ends when his left edge passes the far edge; the take-off ground is remembered across frames. Full flyrun suite: 67 passed.

## Smoke run A: default knobs, senses v2 + motor v2, σ 0, from the start (`runs/S2b_smoke_log.csv`, `runs/S2b_jumps.csv`)
**max_x 899, ended "stuck" at pipe 4 (H 48 @ 912), x 898**, 770 frames, 0 Left presses, 2 blind presses. (S2, before these fixes: 1127, died in pit 1.)

| pipe | S2 | S2b (now) |
|---|---|---|
| pipe 1 (H 32 @ 448) | 2 jumps (first held 4 frames, short) | **1 jump** (take-off x 398, d 40, A held 9 frames, landed on it at x 438) |
| pipe 2 (H 48 @ 608) | 2 jumps | 2 jumps (first: d 60, held 15, landed 2 px short at x 594; second: d 2, held 15, on it) |
| pipe 3 (H 64 @ 736) | 1 jump | **1 jump** (d 2, held 26 frames) |
| pipe 4 (H 48 @ 912) | 2 jumps | **never cleared**: 6 identical jumps from x 898, d 2, 14–15 frames, no progress; the run ends stuck |

So "does each pipe clear in ONE jump?" **No**: pipes 1 and 3 do, pipe 2 needs two (the first take-off at d 60 lands 2 px short), pipe 4 never clears.

**Why pipe 4 fails** (frames 601–636): A is held while the feet are below the pipe top (y 176 → 128, 15 frames), then the face height becomes 0 exactly when his feet reach y 128 and TTMn collapses (0.40 → 0.24 → 0.07, "loom faded" at frame 616). Releasing A lowers the apex (y 119), but x stays 898: Right is pressed the whole time (`R+A`, then `R`), so he is still blocked by the pipe's side although his feet are 9 px above its top. My reading, untested: the real wall contact is at about 14 px (his box is wider than the 12 px `MARIO_BOX` I derived from enemy contact; he touches the pipe at a gap of 2) and he needs more clearance above the top than "feet at the top" to slide over it. Pipe 3 (64 px) clears because the longer hold gives a taller rise. The new rule's release point is "feet above the top"; for a 48 px pipe that is too early. (Not tuned: the spec says so exactly.)

## Smoke run B: pit 1, ASSISTED (scripted driver to x 1000, then the fly; `runs/S2b_pit_assisted_*`)
The unassisted run never reaches pit 1, so I added a disclosed assisted run: the scripted driver (`takeover_x=1000`, assisted/diagnostic only, as in the Part 4 tests) walks and jumps until he is on the ground at x ≥ 1000, then the fly takes over. **He does not cross pit 1: max_x 1127, died in the pit.** One fly jump: take-off x 1073 (d 20, θ 44°), A held **7 frames**, released at frame 706 ("loom faded").

The pit-below rule itself works: from frame 711 on (x 1094, over the first pit tile) the chosen threat is the pit tile under him with d 0 and θ 2.89 rad on every frame until he falls in, TTMn 0.32–0.45 (above threshold). But A was already up: while he rises, the *ahead* tile's 2-D gap grows (d 17 → 39 px over frames 701–710 because the pit surface is 30–40 px below him), θ falls 0.85 → 0.40, TTMn drops under threshold at frame 706, A is released, and a jump cannot be re-pressed in the air. The loom for the pit-under-him arrives 5 frames after the release. So the fix 2 as specified does not rescue this jump; what would is the same rule applied earlier (e.g. ahead tiles also at surface gap with his vertical separation ignored), but that is a spec change for you to decide, not something I tested.

## New death map
| x | what | why |
|---|---|---|
| 898 | stuck at pipe 4 (H 48) | the fly-held jump is released when his feet pass the pipe top (9 px of margin), he does not get over it; repeats until the stuck timer |
| 1127 (assisted) | pit 1 | the ahead-pit loom fades during the rise, A released 5 frames before the under-the-feet pit threat starts |

Clip: `clips/S2b_fixes.mp4` (8.3 s at 0.5×): pipe 1 jump from the unassisted run, then the assisted pit 1 attempt (labelled on screen).
