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
