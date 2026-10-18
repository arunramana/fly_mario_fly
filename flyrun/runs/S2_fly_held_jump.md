# S2 — the fly-held jump (motor v2) (flyrun)

`Knobs.MOTOR_VERSION` "v1" (default, A_HOLD + COOLDOWN, all Part 1–7 results) | "v2" (`motor.Muscle2`, requires `SENSES_VERSION` "v2", asserted in `run.py`). New knob `RELEASE_THRESH` (INVENTED (fixed), default None = TTMN_THRESH, untuned). Full flyrun suite: 62 passed (56 before + 6 new in `tests/test_motor_v2.py`); v1 untouched (r3 and 7e replays still match). `diagnose7b.capture`'s `decide` wrapper now forwards keyword arguments (needed for the v2 motor); the 7b/7d/7e behaviour is unchanged.

## Airborne address (verified empirically)
`0x001D` (player float state), logged every frame through the whole of 1-1 with the scripted driver (3161 frames to the flag): **0 = on ground (683 frames; y always a surface height 176/112/144/…, vertical speed 0 in all of them), 1 = in the air (1258), 2 = 64 frames I did not identify (never needed: the rule uses "not 0")**; there is no grounded frame where y changes. The takeoff shows up 2 frames after the A press (A down at 151, state 1 from 153), the landing frame is the first state-0 frame (y 110 → 112, state 1 → 0). The rule uses `airborne = (0x001D != 0)` read at the start of each frame (the state before the action).

## Motor v2 as built
Press: grounded AND TTMn ≥ TTMN_THRESH AND A not down. Hold: A stays down while TTMn ≥ RELEASE_THRESH. Release: TTMn below it ("loom_faded"). Landing reset: on airborne → grounded A is up for exactly that one frame ("landing_reset", logged only if A was still down); the press rule applies again from the next frame. No hold counter, no cooldown. Right/Left/steering unchanged (a held A with no direction is still dropped, as in v1). Left presses are counted per episode (`left_presses`, `left_frames`; `LEFT_PRESS_WARNING` in the summary if > 0).

## Smoke run (default knobs, senses v2 + motor v2, σ 0, noop 0; `runs/S2_smoke_log.csv`, `runs/S2_jumps.csv`, `clips/S2_fly_held_jump.mp4` = 14.9 s at 0.5×, first three obstacles and on to pipe 2)
**max_x 1127, died in pit 1** (x 1104, W 32), 773 frames, A_frac 0.14, 2 blind presses, **0 Left presses**. Before v2, the same default knobs with v1 senses + v1 motor got stuck at pipe 3 (x 722); with v2 he is past pipes 1–4 and the first Goomba cluster.

First 5 jumps (A onset while grounded → landing):

| # | take-off x | threat (kind id) | take-off d | frames A held | released by | landing x | outcome |
|---|---|---|---|---|---|---|---|
| 1 | 280 | goomba enemy:0 | 20 px (θ 44°) | 12 | loom faded | 309 | no contact (not stomped, survived) |
| 2 | 398 | face 448 (pipe 1) | 40 | 4 | loom faded | 434 | short of the pipe (3 px) |
| 3 | 434 | face 448 | 2 (θ 166°) | 10 | loom faded | 444 | landed on the pipe |
| 4 | 538 | face 608 (pipe 2) | 60 | 4 | loom faded | 578 | short of the pipe |
| 5 | 582 | face 608 | 16 (θ 113°) | 15 | loom faded | 602 | landed on the pipe |

All 10 jumps of the run were released by "loom faded" in the air; **no jump ever reached the landing reset** (A was never still down at a landing in this run), so that code path is covered by the synthetic tests only. Pipes are jumped in two tries (a short take-off at 40–60 px that falls short, then a second one at 2–16 px that makes it); the first try holds A only 4 frames because TTMn crosses 0.30 at θ 44° and the loom falls away as soon as he leaves the ground (my reading, not tested: a face's height above his feet shrinks as he rises, and its θ with it), so the fade is quick.

## Death map (the run has one death)
x 1127, **pit 1**, jump #10 at take-off d 20 (pit tile at 1104): A held only **7 frames** (TTMn peaked 0.26 at the take-off then fell below 0.30 within the jump: the pit tile's θ falls with height, and once his left edge passed the tile the chosen threat switched to a Goomba 182 px away, TTMn 0.19 → 0.06), so the jump was short and he dropped into the pit at x 1122. Mechanism: the loom drive for a pit disappears the moment he is above/over it, so a fly-held jump over a pit ends early — a property of the S1 pit sense × the S2 hold rule, not a bug I could see in either (no tuning allowed in S2).

## Notes
- Jump outcome labels are heuristic (stomp = an enemy's state byte flipping to 4 during the jump; "short of / on the face" = landing x + 12 vs the face's x); the per-frame log is the ground truth.
- Held-jump durations (4–25 frames) are shorter than v1's 12–31 frame holds for faces and pits, longer for the Goomba; there is no frame cap.
