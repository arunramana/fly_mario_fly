# SPEC: 1-1 innate baseline (integration scene)

Status: written before any run. Wiring only: no new circuit code, no new brain scalars. This is a BASELINE, not a criterion:
there is no pass/fail and no threshold. It records what the fixed, innate fly does in the real game so later phases have a
reference.

## Scene
Real SMB level 1-1 from `env.reset()` (power-on). No scripted actions, no enemy clearing, no RAM edits (the scene manifest
`brain/scenes/b11_baseline.json` has an empty action log and no rules; `brain/baseline.py` never calls `apply_rules` and never
writes RAM). The fly takes over on the first frame.

## Brain
`BrainPolicy` with `SenseSettings.user_default()` (brain/settings.py): looming + pursuit (power-up kind only, PURSUIT_AROUSAL as
set) + home landmark (GOAL_CUE_SALIENCE as set), all ON. Calibration `343d8f60abcdba25`. Library id `B11` lists the mechanisms
("looming", "pursuit", "goal_direction"), so `settings_for("B11")` keeps all three. Honest labels: the home landmark is an
invented world cue (moves "go right" into the senses), and this is a baseline, not a criterion.

## Arms and seeds
real, shuffled (degree-preserving, shuffle seed 1 + i), shuffled_class (class-preserving, shuffle seed 1 + i). Fresh noise seeds
6000-6019, same noise seed in every arm, run once. Disclosure: seeds 6000-6029 were used by the Phase 3b investigator as noise
seeds for diagnostic closed-loop runs on the E1 scene (docs/INVESTIGATION_phase3b.md). Different scene, but not unseen seeds.

## Conventions (invented, registered in brain/scalars.py, regenerate docs/SCALARS_BRAIN.md)
- `BASELINE_MAX_FRAMES` = 3000 (50 s). Invented bound; level 1-1 is ~3150 px, so a walker at ~1 px/frame could finish.
- `BASELINE_STUCK_FRAMES` = 300 (5 s). Stuck = no new max_x for this many frames; the episode ends there.
- `BASELINE_TAP_MAX_FRAMES` = 2. Tap = first A run of <= 2 frames (the Phase 3b investigation's definition).
The bootstrap is `tool.core.evaluation.bootstrap_ci` as is (2000 resamples, fixed rng); the 16 px Goomba width is E1's `SPRITE_PX`.
Nothing is tuned on game outcomes.

## Metrics (outcome-neutral, fixed here)
1. max_x: Mario's max world x (page*256 + x). Mean with a percentile-bootstrap 95% CI (continuous variable), median, min/max.
2. End reason, first matching, read from RAM and the env info:
   - `level_complete`: env info `flag_get`.
   - death = game-engine state byte 0x000E == 0x0B (dying; the env reports `done`). Classified on that frame:
     `died_pit` if Mario's vertical viewport byte 0x00B5 > 1 (below the screen); else `died_enemy` if an active non-power-up
     enemy slot lies within 24 px horizontally and 32 px vertically of Mario; else `died_other` (e.g. time up).
   - `stuck`: no max_x progress for BASELINE_STUCK_FRAMES frames.
   - `timeout`: BASELINE_MAX_FRAMES reached.
3. Goombas jumped. [SUPERSEDED by "Metric correction 2026-10-04" below.] A Goomba instance is a slot (type 0x06) from the frame it becomes active until it becomes inactive. It
   "overlaps" while |dx| < 16 px. Closing an overlap window counts the instance as jumped if Mario was airborne
   (player float state 0x001D != 0) on at least one frame of the window and either (a) the slot became inactive while the window
   was open (stomped and removed), or (b) dx fell to <= -16 (the Goomba is behind Mario: passed) with Mario alive and no frame in
   the window with box overlap while Mario stood on the ground (a hit; a stomp overlaps while he is airborne). Instances whose window closes by Mario's death are not jumped. Also reported: Goombas
   encountered (windows opened).
4. Tap fraction: among episodes in which A was pressed at least once, the fraction whose first A run is <= 2 frames; plus the
   A-run length histogram pooled over all runs (1, 2, 3-5, 6-10, 11+) and every run's length stored per episode.
5. Power-up reached: Mario's size state (0x0756) changed from its initial value (mushroom collected); also records whether a
   power-up object was ever released (active slot of type 0x2E).
6. gf_output_max_hz, ttmn_max_hz (as E0/E3); also frames, Left/Right/B/A frame counts, gf_fired.
Per arm also: level_complete count with Wilson CI, and end-reason counts.

## Files
- NEW `brain/baseline.py` (episode, per-episode result, pure metric helpers, evaluation, CLI), `brain/scenes/b11_baseline.json`,
  `tests/test_baseline.py`.
- ADAPTED: `brain/e1.py` / `brain/goal_eval.py` patterns reused (`_row`, `arm_of`, the job/pool/summarize layout); not edited.
- Small edits: `brain/scenes.py` (scene id), `brain/library.py` (entry B11, runnable), `brain/scalars.py` (+3 invented),
  `docs/SCALARS_BRAIN.md` (regenerated), `tool/core/brain_runner.py`, `tool/ui/brain_runs.py`, `tool/ui/tabs/results.py`
  (dispatch to baseline; display of a baseline summary), `tool/tests/test_brain_tool.py` where needed.

## Validation
Unit test on a fake episode for the metric helpers (end reason, jumped Goombas, A runs, tap fraction). A test that the scene has
no rules/log and the module has no enemy clearing or RAM writes. One smoke episode, seed 9100, real arm only. The 20-seed run is
done by the experimenter.

## CLI
`python -m brain.baseline --n 20 --seed0 6000 --workers 8 --out result.json [--arms ...] [--max-frames N]`

## Metric correction 2026-10-04 (Goombas jumped)
Defect: the original definition counted a ground box overlap anywhere in the window as a hit, including the approach frames before
take-off (Mario on the ground at |dx| < 16, box overlapping, a frame before the jump). Real-arm seed 6002 clearly jumps a Goomba
(airborne frames 104-119, survives) yet scored 0; all 7 survivors were false negatives. Chosen outcome-neutrally before re-scoring.
New definition (the rest of item 3 is unchanged): a Goomba instance counts as jumped if Mario is airborne (0x001D != 0) on at least
one frame while |dx| < 16 AND Mario is not killed by it, i.e. the window closes by (a) slot inactive while open (stomp) or (b) dx <= -16
with Mario alive. A "ground hit" is a 16 px box overlap in both axes (as the death classifier and `is_contact`) while Mario is on the
ground AFTER he has been airborne in that window (landing into it); a ground overlap before his first airborne frame in the window
(approach, take-off frame) is not a hit. Walking into a Goomba and dying on the ground, or dying having never been airborne, is not
jumped (a dying Mario closes no window).

Clarification (2026-10-04): "Chosen outcome-neutrally before re-scoring" above is softened to: found in a spot check, fixed before any re-score. The original wording is kept for history.

## Obstacle expansion on (2026-10-05)
From this date the baseline B11 runs with obstacle expansion ON (docs/SPEC_e2a.md): the library entry B11 lists `expanding_obstacle`, so
`settings_for("B11")` sets `SenseSettings.obstacle_expansion`. Static obstacles ahead (pipes, blocks, steps) are then seen as looming at
LC4/LPLC2 (a Mario's-eye-view assumption; no source for obstacle-triggered jumps in flies). Nothing else changes: same scene, same
metrics, same conventions, same arms, no motor-map, calibration or threshold change.
- The result recorded earlier (seeds 6000-6019: real max_x 357, 13 die at the first Goomba, 7 stall at pipe 1, 0/20 complete) stays on
  record as the **baseline without obstacle expansion**. Nothing is edited; re-running with `obstacle_expansion` False reproduces it
  (E0/E1/E3 stamps and results are unchanged because the settings key is written only when true).
- The ON baseline is re-run once on **fresh seeds 6100-6119** by the experimenter. CLI: `python -m brain.baseline --n 20 --seed0 6100
  --workers 8 --out result.json` (the default `--seed0` is now 6100; `--seed0 6000` still runs the old seeds). The result is reported
  next to the earlier baseline, not instead of it.
- Disclosure: the obstacle cue is geometry from the visible tile map for ALL static obstacles of 1-1, not pipe 1 only; tile ids
  other than the ones measured on the first 900 frames (pipes, bricks, ground, "?") are unchecked (coins, hidden blocks).
