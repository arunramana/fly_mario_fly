# Investigation: the GF lead (6.1 frames in the calibration vs 3.3 in the game)

Date 2026-10-06. Report only: no code, config or calibration changed. Scratch: `audit/p13l_a.py`, `p13l_b.py`, `p13l_c.py` (run with `.venv`). Replays read-only, seeds 9300-9302 (non-eval), 1 process. Tags: M measured, C read from code, I inferred.

## Answer
1. 6.1 frames is not a simulated disc result. It is `(l/v)/tan(20 deg)` for l = 8 px, v = 3.6 px/frame (l/v = 2.22 frames = 37 ms), i.e. the time-to-collision at theta = 40 deg on the formula `theta = 2 atan((l/v)/tau)`, where tau = 0 means d = 0 and theta = 180 deg [C: `brain/disc.py:30`; M arithmetic]. It first appears in `docs/INVESTIGATION_stimulus_geometry.md` 1g, not in calibrate.py or SPEC_brain_core.md (grep: no other source). Nothing in the calibration uses it.
2. The gap is contact geometry, not speed: the GF fires at the same d = 22, theta = 40 deg as the disc predicts, but the Goomba kills Mario at d = 9 (hitbox overlap, theta = 83 deg then), not d = 0. 22/3.6 = 6.1 frames to d = 0; (22 - 9)/3.6 = 3.6 (12 px/3.6 = 3.3 with the d - 10 gap convention). The whole 2.5-2.8 frame difference is the 9-10 px offset divided by the closing speed.
3. The calibration target (theta = 40 deg, `THETA_GF_DEG`; threshold = mean GF membrane at 40 deg over discs l/v 20/40/80) is an ANGLE. It implies no time. At 40 deg the time to the disc's d = 0 is 2.75 * l/v: 3.3 / 6.6 / 13.2 frames for l/v 20/40/80 (4x range) [M, `p13l_b`].
4. Implication for fast closers: with a fixed angle, lead time shrinks in proportion to l/v (closing speed). The game's B11 Goomba at 3.6 px/frame is l/v of about 37 ms, between discs 20 and 40, and has only 3.3-3.6 frames after the spike. Whether that is "too late" is an outcome question, not answered here.

## Table (measured unless tagged)
| scenario | theta at first spike (deg) | d at spike (px) | closing speed (px/frame) | dtheta/frame at spike | frames spike -> disc end (d=0 / tau=0) | frames spike -> Goomba hitbox contact (d=9) | spike -> lift-off |
|---|---|---|---|---|---|---|---|
| disc l/v 10 | 47.2 | n/a (tau 22.9 ms) | n/a | 18.8 deg | 1.37 | n/a | n/a |
| disc l/v 20 | 47.2 | n/a (tau 45.8 ms) | n/a | 11.7 | 2.74 | n/a | n/a |
| disc l/v 40 | 40.6 | n/a (tau 108 ms) | n/a | 5.05 | 6.48 (exact 40 deg: 6.58) | n/a | n/a |
| disc l/v 80 | 43.6 | n/a (tau 200 ms) | n/a | 3.07 | 11.97 (exact 40 deg: 13.16) | n/a | n/a |
| E1 standing Mario, Goomba walking (seeds 9300/01/02) | 41.7 / 40.0 / 40.0 | 20 / 22 / 22 | 0.6 (5-frame mean) | 0 / 1.6 / 1.6 | I: 22/0.6 = 36 | 17 / 20 / 20 (d <= 9 frame minus spike) | A at +0 / +4 / +4, lift-off +1 / +5 / +5 |
| B11 walking-right Mario, Goomba (seed 9300) | 40.0 | 22 | 3.6 (d: 25,22,18,14,11,7) | 4.5 (35.5 -> 40.0) | I: 6.1 | 3.5 (d=9 between frames 105 and 106) | A at +1, lift-off +2 |
| B11 seeds 9301 / 9302 | 47.9 / 47.9 | 18 / 18 | 3.6 | 7.9 | I: 5 | 2.5 | A at 0 / +1; 9302 died at +3 |
| pipe 1 running approach (M0, synthetic, from `p12g_g_final.json` and RESULTS_e2a) | 41.4-43.7 | 28-31 | 3.0 (running) | n/a (not re-measured) | n/a | stall d = 14: 4.7-5.7 frames to stall; A 5-8 px before stall (1.7-2.7 frames) | n/a |

Notes. B11 and E1 columns "frames to disc end" are inferred (not a game event). E1 "frames to contact" uses the first frame dx <= 9; E1's own `is_contact` (|dx| < 16) fires 16-26 frames after the spike. In E1 Mario jumps and stomps; no death. Pipe 1 numbers are from earlier sprints, not re-run here.

## Evidence
| claim | source | confidence |
|---|---|---|
| 6.1 = (8/3.6)/tan 20 deg, never simulated | `audit/p12g_k.py` last print; disc formula `brain/disc.py:30` | M/C high |
| Calibration averages GF membrane at theta = 40 deg over l/v 20/40/80; no time quantity | `brain/calibrate.py:68-71`, `calibration.py:32-33` | C high |
| Real disc spike angle 47.2/47.2/40.6/43.6 (this run, seed 9300; docs quote 47.2/47.2/47.2/40.6 across probes) | `p13l_b` | M |
| Spike angle exceeds 40 deg most when dtheta/frame is large (18.8 and 11.7 deg/frame -> 47.2; 5 and 3 -> 40.6, 43.6): the GF integrates over a few frames, so it lags the angle at fast growth | `p13l_b` | M for the pattern, I for the mechanism |
| Goomba contact is d = 9, theta 83 deg there | `INVESTIGATION_stimulus_geometry.md` 1d (not re-measured) | M |
| B11 closing 3.6 px/frame = Mario 3.0 + Goomba about 0.6 | `p13l_a` (d series), 1e | M |
| E1 closing speed 0.6 px/frame, 15-20 times slower than B11; theta 40-41.7 at the spike, i.e. the same angle | `p13l_c` | M |
| Ache 2019: the paper exists and says GF spike timing encodes size/velocity (LPLC2 size, LC4 velocity). The "about 40 deg" figure was NOT re-verified here (full text 403) | search result | abstract only; calibration.py comment says verified, unchecked this sprint |

## What this means for the plan
- The 6.1 is a modelling artefact of the divergent disc (contact at 180 deg), so it should not be quoted as a calibration target; the calibration never used it. It restates the earlier finding (stimulus-geometry item 1): the open choice is the contact convention (d=9 hitbox vs d=0), not the GF threshold.
- 40 deg is an angle, so the threshold is speed-agnostic by construction. In the game the angle is reached at the same d = 22 for a 0.6 and a 3.6 px/frame closer; lead time scales 6x between E1 and B11 (17-20 frames vs 3.5). The E1-vs-B11 survival difference is thus partly a lead-time consequence of an angle rule, an inference not tested here.
- The disc spike angle varies 40.6-47.2 with l/v (spread 6.6, inside the 38-48 gate); game values 40.0-47.9 sit in the same band, so no inconsistency with the gate.

## Open questions
- Which of Ache 2019 / von Reyn work actually reports an angle (rather than a time) threshold for the GF, and at what l/v? Not verified; a time-based or l/v-dependent threshold would change the justification.
- Why 9301/9302 spike at 47.9 deg (d 18) while 9300 spikes at 40.0 deg (d 22): 1-frame noise-driven spike jitter at 4-8 deg/frame; not investigated further.
- Pipe approach dtheta and frames were not re-measured this sprint.
