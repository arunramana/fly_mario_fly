# 031 -- jump.jump_cooldown_frames sweep (`win_attempt`, no code changes)

**Setup.** `win_attempt` duplicated from `legacy`. Level 1-1, sigma=0.0, seed=0,
max_frames=3000, `raw_frames`/`record_video`/`brain_panel` all off. Six values
of `jump.jump_cooldown_frames` (default 40), run in parallel through
`tool/core/runner.run_one()` under one `multiprocessing.Pool(6)`
(`OMP_NUM_THREADS=1`/`OPENBLAS_NUM_THREADS=1`/`MKL_NUM_THREADS=1`, spawn
context) -- the same warm-parallel pattern `tool/core/batch.py` uses
internally, just varying `config.jump.jump_cooldown_frames` per task instead
of seed. Wall clock: 85.3s for all six runs together. Telemetry CSVs for
each variant are in `projects/win_attempt/telemetry/031_cooldown<N>_
telemetry.csv`.

## Results

| cooldown | outcome | frames | max_x (death x) | cause |
|---:|---|---:|---:|---|
| 40 (baseline) | died | 807 | 1425 | pit |
| 30 | survived to max_frames | 3000 | 898 | stall (refusing a 7-tile gap) |
| 20 | died | 658 | 692 | enemy |
| **15** | died | 644 | **1147** | pit |
| 10 | survived to max_frames | 3000 | 1314 | stall (refusing a 7-tile gap) |
| 5 | died | 624 | 680 | enemy |

None of the six reached the flag. Lowering the cooldown is **not**
monotonically good or bad -- it trades one failure mode for another:

- **40 (baseline) and 15** both die to a pit, at the point where the escape
  circuit's shared `jump_cooldown`/`jump_hold` timer happens to reopen well
  after a real gap started shrinking underfoot (the exact mechanism from the
  earlier test1 run #1 analysis: `jump_cooldown_frames + jump_hold_frames`
  after the previous, unrelated commit). 15 dies at a *later* pit and reaches
  a higher max_x (1147) than 20 or 5, but still doesn't clear it -- confirmed
  visually (`cd15_frame_643.png`, saved during this investigation): the last
  frame before death shows Mario off-screen between two consecutive pit gaps,
  matching `gap` telemetry's own 2->1->0 readout right before frame 644.
- **20 and 5** die earlier and shorter (692, 680) to a Goomba, walked into
  head-on (`theta` ramps cleanly to 1.3-1.6, `d_px` shrinks to single digits,
  `gap=0` throughout -- no pit involved). Both show an earlier stretch stuck
  against a wall repeatedly hitting a `?` block (`qblock_hit` toggling while
  `mario_x` holds still) before resuming and walking straight into the
  Goomba -- a *shorter* cooldown didn't give the circuit more chances to
  escape it in time; if anything these are the two worst outcomes of the six.
- **30 and 10** never die at all -- they get permanently stuck refusing a
  7-tile gap (`refusing=True`, `mario_x` frozen) for the last ~2000+ frames.
  A shorter cooldown here just traded "died at a pit" for "survives forever,
  stuck at a wider one," not a win.

**No value in this sweep reaches the flag or clears the pit that kills the
baseline.** Cooldown alone doesn't fix the underlying issue identified in
test1 run #1: the escape circuit's cooldown/hold timer runs on its own
schedule, independent of whether a real, graded threat (a growing gap, an
approaching Goomba) is already visible and worth reacting to sooner.

## The DNp02 finding at frame 613 (test1 run #1) -- the premise doesn't hold

Re-ran the exact deterministic scenario (1-1, sigma=0, seed=0) with the enemy
registry instrumented directly. At frame 613, `mario_x=200`, and the registry
shows a real, active `GOOMBA` record at screen x=229 -- distance +29, exactly
matching that frame's own telemetry `d_px=29`. **There was a real Goomba
there.** It had been closing steadily since at least frame 595 (`theta`
0.17->0.98, `d_px` 94->15 over the next several frames, both moving in
lock-step with an object approaching from ahead) -- a clean, physically
consistent looming signal, not noise or a stale RAM artifact.

So the input that drove DNp02's commit was that Goomba's own genuine
looming (`abs(dtheta)`, fed into `dnp02_ema["L"/"R"]` every frame, per
`bridge/full_policy.py`'s DNp02 input block) -- not "nothing." The premise
in docs/RUNS.md's own note ("commits recurring... with theta=0.000
d_px=None, no real enemy") describes a *different* pattern seen at other
commits in the same run (frames 278 and 548 in this run's own commit table
both show `frames_to_contact=NaN`, consistent with that no-target case) --
it doesn't generalize to every DNp02 firing, and specifically not to 613.

What *is* true, and is the more useful finding: DNp02 (not DNp01) got credit
for this commit purely because it was DNp02's own `ttmn_val_dnp02` that
crossed `ttmn_press_threshold` first at the exact frame the shared
`jump_cooldown`/`jump_hold` gate reopened (613 = 548 + 25-frame hold +
40-frame cooldown, the same arithmetic that explains the fatal 678 commit).
DNp01 -- the pathway that actually receives the gap's own placed current --
was gated by the identical shared timer and never got a chance to compete
for this particular window. Which of the two pathways ends up "solving" a
given encounter is decided by that shared cooldown clock, not by which one
is the more appropriate responder to what's actually on screen.
