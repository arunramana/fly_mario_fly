# RESULTS: 1-1 innate baseline (docs/SPEC_baseline_1-1.md)

This is a BASELINE. There is no pass/fail criterion and nothing is tuned afterwards. One run, no retries:
`.venv/Scripts/python -m brain.baseline --n 20 --seed0 6000 --workers 8 --out audit/p5_b11.json` (network 3848f3e70b2051ef,
calibration 343d8f60abcdba25, scene b11_baseline c38a02f084313ee0, senses: pursuit powerup, goal_cue_salience 15, pursuit_arousal 0.65).
Seeds 6000-6019 were also noise seeds of the Phase 3b diagnostics on a different scene (disclosed in the SPEC). Raw data: audit/p5_b11.json.

| metric (n=20 each) | real | shuffled (degree) | shuffled_class |
|---|---|---|---|
| max_x mean (bootstrap 95% CI) | 357 (333-380) | 40 (40-40) | 40 (40-40) |
| max_x median / min / max | 315 / 315 / 434 | 40 / 40 / 40 | 40 / 40 / 40 |
| level_complete (Wilson CI) | 0/20 (0-16%) | 0/20 | 0/20 |
| end: died_enemy / died_pit / died_other | 13 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| end: stuck / timeout | 7 / 0 | 20 / 0 | 20 / 0 |
| end frames | died_enemy: all 13 at frame 106; stuck: all 7 at frame 446 | all 20 at 301 | all 20 at 301 |
| Goombas encountered (total, per episode) | 20 (1.0) | 0 (0) | 0 (0) |
| Goombas jumped by the SPEC metric (total, per ep.) | 0 (0) | 0 | 0 |
| A pressed in episodes / first-run tap fraction (Wilson) | 20 / 0/20 (0-16%) | 13 / 0/13 (0-23%) | 1 / 0/1 (0-79%) |
| A-run histogram 1 / 2 / 3-5 / 6-10 / 11+ | 0 / 0 / 17 / 3 / 0 | 0 / 0 / 3 / 2 / 8 | 0 / 0 / 1 / 0 / 0 |
| power-up released / collected | 0/20 / 0/20 (CI 0-16%) | 0/20 / 0/20 | 0/20 / 0/20 |
| gf_fired | 20/20 | 20/20 | 0/20 |
| gf_output_max_hz / ttmn_max_hz (max over episodes) | 12.00 / 0.295 | 12.00 / 0.775 | 0.00 / 0.099 |
| Left / Right / B / A frames (mean per episode) | 0 / 225 / 225 / 3.9 | 301 / 0 / 301 / 9.2 | 299 / 2 / 301 / 0.2 |

Plain reading of the numbers:
- Real: 13 episodes die to the first Goomba at x=315, frame 106; 7 survive it (jump one frame earlier) and then stand still at x=434 (stuck
  for 300 frames, the first pipe) with no further A press. Only two distinct trajectories across 20 noise seeds: noise barely changes behaviour.
  Nothing reaches the mushroom (never released, no block was hit), nothing reaches the flag.
- Both shuffled arms walk left into the screen edge (x=40) and stay there; the degree shuffle still fires the Giant Fiber, class shuffle does not.
- The fly can, innately: walk right, commit a jump to the first Goomba when the Giant Fiber fires (about half the time in time), survive it.
  It cannot: clear the pipe, take more than one jump, hit a block, or reach the flag.

## Classifier spot-check (read-only replay, audit/p5_spot.py; per-frame RAM)
The real arm only produces two end reasons (died_enemy, stuck); there is no real-arm died_pit/died_other episode, so 3 different reasons are not available.
- Seed 6000 died_enemy (frame 106): engine byte 0x0E = 0x0B on frame 106, Mario y-high 1 (not a pit), Goomba slot 0 at dx +4, y 184 vs Mario 164. Correct.
- Seed 6002 stuck (frame 446): x=434 flat for 300 frames, alive, no enemies. Correct. died_pit never occurred in any arm, so it is untested on real data.
- Seed 6001 died_enemy: identical to 6000.
- MISMATCH in the "jumped" metric (reported, not fixed): seed 6002 visibly clears the Goomba (airborne frames 104-119, Mario y 138-170 above the
  Goomba's y 184, dx 14 -> -65, Mario survives) but goombas_jumped = 0. Cause: on frame 103 Mario is still on the ground with |dx| = 14 < 16,
  which the tracker counts as a ground "hit" (box width 16) before take-off, so rule (b) never fires. All 7 stuck episodes passed the Goomba the same way,
  so the true count of Goombas physically jumped is 7 (survivors), against 0 reported. The 0 jumped / 20 encountered is an undercount by the metric
  definition; the per-episode end reasons, max_x, A runs and everything else above are unaffected.

## Diagnostic: Goomba deaths vs survivors (replay)
Read-only replay, no code changed, nothing tuned (scripts audit/p6_replay.py, p6_an*.py; per-frame data audit/p6_traj.json). Replay of the already-run
baseline: real arm, seeds 6000-6019, same network/calibration/scene; it reproduces the stored result exactly (13 died_enemy at frame 106, 7 survive).
E1 comparison: real arm replayed on seeds 3200-3219 (Mario starts standing): 16 stomped, 4 died. Convention: "dx" = Goomba world x minus Mario world x in
px, read from RAM before the step of the named frame (what the fly saw); theta = the fly's elevation-weighted angle (2 atan(16/2d)). Take-off = first
frame whose post-step Player_State is airborne (it comes one frame after the first A frame). Everything in the tables is measured unless marked (inferred).

| baseline, real | n | GF spike frame (dx px, theta) | A press frame (dx, theta) | take-off frame (dx, theta) | A run | Mario / Goomba speed px/frame |
|---|---|---|---|---|---|---|
| died_enemy | 13 | 102 x3, 103 x10 (dx 22 / 18, 40.0 / 47.9 deg) | 104 x13 (dx 14, 59.5 deg) | 105 (dx 11, 72.1 deg) | 3 frames, all 13 | 3.0 / -0.5 |
| survived | 7 | 102 x5, 103 x2 (same dx / theta) | 103 x7 (dx 18, 47.9 deg) | 104 (dx 14, 59.5 deg) | 5-7 frames | 3.0 / -0.5 |

Mario runs at 3 px/frame (B held, Right held) the whole approach; the Goomba walks toward him at ~0.5 px/frame (dx falls 22, 18, 14, 11, 7, 4, 0: about 3.5/frame).
Theta at the Goomba rises 40.0, 47.9, 59.5, 72.1 deg on consecutive frames (+8, +12, +13 deg/frame). The first frame with theta >= 40 deg is frame 102 (dx 22);
the GF spikes on that frame or the next. E1 (Mario standing): closing speed ~0.5 px/frame, theta rises 40.0, 41.7, 43.6, 45.7 deg (+1.7 to +2 deg/frame), GF spike frames
108-113 at dx 20-23 (theta 38.4-43.6 deg), A press at dx 15-22, take-off at dx 14-21, A run 1-6 frames.

What separates deaths from survivors in the baseline (measured): only the A frame. All 7 survivors pressed A on 103, all 13 deaths on 104, one frame later
(take-off 104 vs 105, dx 14 vs 11 at take-off). The GF spike frame does not separate them: GF 102 with delay to A of 1 frame = survive, delay 2 = die; GF 103 with
delay 0 = survive, delay 1 = die. The GF-to-A delay (0, 1 or 2 frames, from the TTMn onset and the A muscle's leaky integral) is the only variable that differs, and it
splits the episodes 13/7 (GF 102: 5 of 8 survive, GF 103: 2 of 12; Fisher p = 0.06, only a trend, which is why "noise" is not the whole story: spike frame and delay
both matter). The brain differs across seeds only by noise; there are two trajectories.
Why one frame is fatal: after take-off Mario rises 6, 12, 18 px on the first three air frames (survivor y 170, 164, 158, 153, ...; death y 170, 164 then contact on frame
106 at dx 4 with rise 12). Survivors have risen 18 px by dx 3 and pass; deaths have risen only 12 px at dx 4 and hit. So the fly needs ~3 air frames of lift before the Goomba is
under it: take-off needed at dx >= ~14 (inferred threshold between the observed 14 survive and 11 die), i.e. A press at dx >= ~15-18. Distance at the GF spike (22 or 18) minus that
leaves 4-8 px of slack, about 1-2 frames at a 3.5 px/frame closing speed; the fly's GF-to-A latency is 0-2 frames. The airtime x closing-speed rule of thumb is not the binding
constraint (airtime 17 frames x 3.5 = 60 px, far more than needed); the binding constraint is the rise time to clear 16 px.

Answer: yes, the jump is late because Mario walks into the Goomba. Walking gives 3.5 px/frame closing instead of 0.5 (7x), theta grows 8-13 deg/frame instead of ~2, so the
looming signal crosses the calibrated ~40 deg GF threshold only 22 px away and the whole decision (GF, muscle, A, 3 frames of lift) must fit in ~2 frames. E1 (standing) has the
same GF threshold distance (20-23 px) but ~7x more time, and 16/20 survive. The 4 E1 deaths are a different failure (measured): short A taps (1 frame, rise 24 px, airtime 16) that land at
dx 9-10 as the Goomba arrives (hit on landing); the survivors with the same 1-frame tap stomp it instead (inferred: a 1-frame landing-time difference again).
Inferred, not measured: the exact collision box (taken from where the deaths and survivors fall: contact around dx <= 4 with rise < ~16 px), and the muscle-delay mechanism as the source
of the 0-2 frame GF-to-A variation (not instrumented here).

---
## Corrections and notes (appended 2026-10-04; the rows and text above are not rewritten)

**Goombas jumped (F1).** The table row "Goombas jumped by the SPEC metric: 0 (0)" is the stored count from the run, made with the tracker before correction.
The corrected tracker is commit 2794964 (brain/baseline.py GoombaTracker). Current value: a read-only replay (audit/p7_rescore.py, same noise seeds 6000-6019,
repo .venv; a replay of already-run episodes, not a new eval) re-scores the real arm as **7 jumped / 20 encountered** (7 per-episode jumped = 1 in exactly the 7
stuck episodes 6002, 6004, 6006, 6011, 6012, 6015, 6018; 0 in the 13 died_enemy episodes). The replay reproduced outcome, frames and max_x of every episode.
Shuffled arms encounter no Goombas (0/20 each), so they have no jumped count. Shuffled arms never reach the Goomba, so they cannot be compared with the real arm on jumping (F6).

**"In time" rate (F3).** The line "(about half the time in time)" is imprecise: 7 of 20 = 35% of episodes jumped in time (13/20 = 65% did not).

**Diagnostic section corrections (F4).** The sentence "only the A frame ... is the only variable that differs" overstates. What is measured: the 13/7 split is explained by one
frame of A timing (survivors pressed A on frame 103, deaths on 104). Attributing that frame to the GF-to-A delay (muscle integral) is post-hoc, from n=20 episodes that
form only two trajectories, Fisher p = 0.06 (a trend, not significant), and was not tested (the muscle mechanism is not instrumented). "Only variable" is withdrawn.

**Scratch scripts (F5).** The audit/ scripts (p5_spot.py, p6_*.py, p7_rescore.py) and their JSON outputs are scratch and gitignored (audit/ is in .gitignore); they are not committed artefacts.
