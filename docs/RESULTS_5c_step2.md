# Phase 5c step 2 (pursuit azimuth -> 0): validation results

Run 2026-10-06 by the experimenter, `.venv/Scripts/python.exe`, each run once, 3 workers, no code/config edits. Raw: `audit/p14_e3.json`, `audit/p14_b11.json`; replay scripts `audit/p14_d.py` (E3 seed 9200), `audit/p14_b.py` (B11 seeds 6300, 6301, 6307).

## 1. Affected tests
`tests/test_phase3.py tests/test_e1.py tests/test_baseline.py tests/test_scalars_doc.py`: 50 passed, 0 failed (690 s). The implementer's 6 uint8 OverflowErrors came from the wrong interpreter; none under `.venv`.

## 2. E3 (seeds 5300-5319), criterion SPEC_phase3 s13
| arm | reached (Wilson 95%) | end | median frames | GF crossed | GF / TTMn max Hz | mean Left frames |
|---|---|---|---|---|---|---|
| real | 20/20 (84-100%) | 0 deaths, 0 timeouts | 116 | 0/20 | 0.00 / 0.013 | 0.0 |
| degree shuffle | 0/20 (0-16%) | 20 timeouts | - | 9/20 | 9.00 / 0.312 | 109.7 |
| class shuffle | 2/20 (3-30%) | 18 timeouts | 101 | 0/20 | 0.00 / 0.050 | 75.7 |
| real_no_pursuit | 0/20 (0-16%) | 20 timeouts | - | 0/20 | 0.00 / 0.013 | 0.0 |

Criteria: real >= 14/20 pass; degree shuffle <= 2/20 pass; class informative only (2/20); no_pursuit fails as expected (0/20). Previous E3 (5200-5219): 20/20, 0/20, 3/20, 0/20: same within noise.

## 3. B11 (seeds 6300-6319), no pass/fail
| arm | max_x mean (bootstrap 95%) / median | ends | Goombas jumped / encountered | tap fraction | A-run hist (1/2/3-5/6-10/11+) | GF fired | power-up |
|---|---|---|---|---|---|---|---|
| real | 374 (315-451) / 315 | died_enemy 18, stuck 2 | 5/23 (3 episodes) | 0/20 | 3/0/18/7/6 | 20/20 | 0 released, 0 collected |
| degree shuffle | 40 / 40 | stuck 20 (x=40) | 0/0 | 0/13 | - | 20/20 | 0 |
| class shuffle | 40 / 40 | stuck 20 (x=40) | 0/0 | 0/1 | - | 0/20 | 0 |

Real: deaths at x 315 (16 episodes), 677 (6307; died at the next obstacle/Goomba after surviving the first); stalls at x 724 and 723 (6301, 6319). Pipe 1 cleared in 3/20 (6301, 6307, 6319; the same three that survived the first Goomba). First GF spike frame 102-103 in all real runs. Replays: seed 6300 first spike at d=18 px, theta 0.836 rad (47.9 deg), A pressed at d=14, Goomba contact at d=7 (lethal); seed 6307 first spike at d=22, theta 0.698 rad (40 deg).
Earlier baseline (obstacle expansion on, 6100-6119): mean 417, 15 died at the Goomba, 5 stalled at x~724. Dose-response at value 15 (6200-6219): mean 466, 8 survivors. Now: mean 374, 3 survivors of the first Goomba. Different seeds; two of the first-Goomba trajectories are near-identical across seeds (x 306 at frame 103), so the effective sample is small.

## 4. What E3 keys on after the tilt is gone (seed 9200, real arm replay)
- Pursuit azimuth is exactly 0.0 in all 85 pursuit calls; LC10a left drive == right drive in every call (0.0029 first, 3.29 mid, 5.2 last; both sides equal). There is no left/right asymmetry from the object.
- Pursuit target appears from about frame 37 (target dx 43 px); no_pursuit has no calls and Mario does not move at all (x=330 for 150 frames, mushroom walks past).
- Real arm: stands at x 330 until frame ~81, then walks right (x 339 at f91, 355 at f100, 378 at f109), contacts the mushroom at frame 116 (x 399), with Right 38 frames, Left 0, B 38, no A, GF silent. DNa01 0, DNa02 0.1 at all times.
- Why it still approaches: both LC10a sides driven equally by pursuit (a symmetric, growing drive as the object gets salient) plus, in E3, no home landmark (E3 goal_cue_salience 0.0). The forward walk begins only when the symmetric drive crosses the motor threshold; direction right is not carried by any visual asymmetry now. I did not isolate whether the walk-right comes from the motor map's default asymmetry (DNa02 0.1 > DNa01 0.0) versus the object; that is a hypothesis, not measured. The shuffles, with the same drive, walk Left (degree 109.7 mean Left frames) and never reach: the real wiring's right-turn bias (or motor map readout) is what produces "right", not the stimulus.

## 5. Verdict
E3: the same (20/20, 0/20, 2/20, 0/20). B11: not distinguishable from before, nominally slightly worse (mean 374 vs 417/466, 3 survivors vs 5-8), within seed noise at n=20; same failure mode (the GF fires at d 18-22, the jump is too late for the first Goomba; stall at x~724). Step 2 did not make Mario better; E3 unchanged, B11 nominally worse. No video: no qualitative behaviour change.
