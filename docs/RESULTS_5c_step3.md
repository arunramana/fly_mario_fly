# Phase 5c step 3 (obstacle face as an extended object): validation results

Run 2026-10-06 by the experimenter, `.venv/Scripts/python.exe`, each run once, 3 workers, no code/config edits. Raw: `audit/p15_e2a.json` (+ `.log`), `audit/p15_b11.json` (+ `.log`), replay scripts `audit/p15_replay.py`, `audit/p15_replay2.py` (+ `p15_replay.log`, `p15_replay.json`). `tests/test_e2a.py`: 22 passed (152 s).

## 1. E2a, fresh seeds 7200-7219 (criteria from docs/SPEC_e2a.md)
| arm | cleared (Wilson 95%) | ends | GF fired / before face | GF x, d, theta (median) | first A x (median) | take-off x (median) | first A-run median, taps | GF / TTMn max Hz |
|---|---|---|---|---|---|---|---|---|
| real | 20/20 (84-100%) | cleared 20 | 20 / 20 | x 407 (404-410), d 41 (38-44), 42.6 deg (40-45.7) | 414.5 (410-419) | 417.5 (413-422) | 12 (1-14), taps 5/20 (25%) | 15.0 / 0.371 |
| degree shuffle | 0/20 (0-16%) | timeout 20 | 20 / 20 | x 321, d 127, 14.4 deg (all 20 identical) | 321 (13 runs) | 321 | 17, taps 0/13 | 12.0 / 0.833 |
| class shuffle | 0/20 (0-16%) | timeout 19, stuck 1 | 0 / 20 | - | 321 (1 run) | 321 | 4, 0/1 | 0 / 0.101 |
| real_no_obstacle | 0/20 (0-16%) | stuck 20 | 0 / 20 | - | none | none | no A | 0 / 0.012 |

Criteria: real >= 14/20 PASS; degree shuffle <= 2/20 PASS; class informative (0/20); no_obstacle <= 2/20 PASS. Context only, previous E2a (7100-7119): 18/20, 0/20, 0/20, 0/20. The 2 old failures (1-frame taps) are now 5 taps of which none failed.

Real arm, stall point = face 448 - 14 = x 434: GF first spike 24-30 px before the stall point (median 27), first A 15-24 px before (median 19.5), take-off (first airborne) 12-21 px before (median 16.5). Taps (A-run 1-2 frames) 5/20, longer holds 11-14 frames in 15/20.
Is the GF too early on pipe 1? In the game, no: GF d 38-44 px (theta 40-46 deg) is the predicted 43, and the GF-to-take-off lag is about 10 px; take-off is 12-21 px before the stall point, inside the 5-29 window for a tap; for the 15 longer holds (11-14 frames) the windows quoted (35-65) are not met by take-off distance (12-21 px), but all 20 cleared. No parameter adjusted.
Surprise (reported plainly): the degree-shuffle GF fires at frame 0 in 20/20 (x 321 = start, d 127, theta 14.4 deg) and A is pressed in 13/20 while Mario never advances (max_x 321, timeout); same as the synthetic note (landmark alone drives the shuffled net). Shuffled does not walk, so the 0/20 does not test the face detection (the same limitation as in 223).

## 2. B11, fresh seeds 6400-6419 (no pass/fail)
| arm | max_x mean (bootstrap 95%) / median | ends | Goombas jumped / encountered | taps | A-run hist 1/2/3-5/6-10/11+ | GF fired | power-up | GF / TTMn max Hz |
|---|---|---|---|---|---|---|---|---|
| real | 385 (343-441) / 315 (range 315-596) | died_enemy 15 (all x 315, frame 106), stuck 5 (all x 596, frame 500) | 5 / 20 (5 episodes) | 0/20 | 4/3/18/0/15 | 20/20 | 0 / 0 | 15.0 / 0.351 |
| degree shuffle | 40 / 40 | stuck 20 (x 40) | 0/0 | 0/13 | - | 20/20 | 0 | 12.0 / 0.777 |
| class shuffle | 40 / 40 | stuck 20 (x 40) | 0/0 | 0/1 | - | 0/20 | 0 | 0 / 0.100 |

Real: pipe 1 (x>479) cleared 5/20 (the 5 Goomba survivors, 6401, 6406, 6407, 6409, 6413), pipe 2 (x>671) 0/20, pipe 3 (x>767) 0/20. Distinct stall x: 596 only (5/5). Context step-2 B11 (6300-6319): mean 374, 18 died at an enemy, 2 stalled at x~724; 6100-6119: mean 417, 5 stalled at 722-724 (all five had passed pipe 2).
Where they now stall: x 596 is the base of pipe 2 (face about x 608-610). Previously all pipe-1 survivors passed pipe 2 and stalled at pipe 3 (722-724).

## 3. Replay of the previously stuck episodes (seeds 6103, 6105, 6106, 6108, 6115 from the 6100-6119 B11 run; already-used seeds, read-only replay with current code)
| seed | previous | now | where it ends |
|---|---|---|---|
| 6103 | stuck 724 | stuck, max_x 722, frame 542 | base of pipe 3; last A run (37 frames) began x 621 at pipe 2 / Goomba, none after landing at x 722 |
| 6105 | stuck 724 | stuck, max_x 722, frame 542 | same, A run 39 frames from x 621 |
| 6106 | stuck 724 | stuck, max_x 596, frame 500 | base of pipe 2; A held 181-204 (Goomba jump), landed x 594-596, no A afterwards |
| 6108 | stuck 724 | stuck, max_x 596, frame 500 | same |
| 6115 | stuck 724 | stuck, max_x 596, frame 500 | same |
So 2/5 still stall at pipe 3 (x 722) and 3/5 now stall EARLIER, at pipe 2 (x 596). None passes pipe 3. Requested pipe-3 GF d/theta and A-press d: the telemetry rows' `d_px`/`theta`/`spike` columns carry the Goomba slot (d 7-136 px, theta 0.0-0.7 deg, spike mostly 1 as the Goomba stream), not the obstacle face, so the face GF spike d/theta and the A press distance to the face at pipe 3 cannot be read from these rows; what is observed is that in the 2 pipe-3 stalls no A press exists after the landing at x 722 (A 0 for 300 frames), so there is no A-run to compare with the 10-frame need. I did not instrument further (no code edits).

## 4. Verdict
E2a: better or the same (real 20/20 vs 18/20 on different seeds; criteria all met; take-off inside the pipe-1 window). B11: worse at the margin and no better overall: mean 385 vs 374/417 is within seed noise (the max_x of 15/20 is fixed by the first Goomba at x 315), but the 5 survivors that previously passed pipe 2 and reached x 724 now stall at pipe 2 (x 596) in 5/5 here and 3/5 in the replay. Pipe 2 cleared 0/5 (before: 5/5 in 6100-6119). Step 3 helped the pipe-1 scene, did not fix pipe 3 (2/5 still stall at 722), and appears to have moved a stall from pipe 3 to pipe 2 for the remaining. Cause not diagnosed. No video: pipe 3 itself did not change qualitatively (it still stalls, 722); pipe 2 changed, but the rule asked for pipe-3 change only.
