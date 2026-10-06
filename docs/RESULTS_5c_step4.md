# Phase 5c step 4 validation (2026-10-06)

Surface-to-surface distance (d = centre - 10/11), enemy w = 10, obstacle d shifted by 13/14 (docs/SPEC_geometry_5c.md sections 7-8). Fresh seeds, each run once, 3 workers, nothing tuned. Raw: audit/p16_e1.json, p16_e2a.json, p16_b11.json, p16_dose.json; logs audit/p16_*.log.

## 1. E1 (seeds 3300-3319)
| Arm | Survived (Wilson 95%) | GF before contact | theta at GF (median, range) | surface d at GF | Criterion | Result |
|---|---|---|---|---|---|---|
| real | 10/20 (30-70%) | 20/20 | 42.1 deg (39.3-45.2) | 13 px (12-14) | >= 16 | FAIL |
| degree shuffle | 0/20 (0-16%) | 0/20 | none | none | <= 2 | pass |
| class shuffle | 15/20 (53-89%) | 20/20 | 32.8 deg (29.5-34.7) | 17 px | informative | informative (fires early, survives) |
| lesion_gf | 0/20 (0-16%) | 20/20 (spike, output 0 Hz) | 42.1 | 13 | fails | pass |
Context: step 3-era E1 on 3200-3219: real 16/20, degree 0/20, class 16/20, lesion 0/20. Real is WORSE (10 vs 16 on different seeds; CIs overlap but the criterion is missed).
Frames GF spike to contact (real): median 19, range 15-26 (survived ones 17-26, died 15-19). A-run lengths (a_frames): 10 of 20 are <= 6 frames (2,2,2,2,2,3,3,4,4,6), 10 are 14-21. Every one of the 10 deaths is a short press (2-6 frames); every survivor is a long hold (14-21). GF output 18 Hz max, TTMn max 0.40 Hz (real). Class shuffle holds 7-38 frames, 15/20 survive.
In-game centre d at spike = surface + 10 = about 23 (predicted 23.7).

## 2. E2a (seeds 7300-7319; stall point x 434)
| Arm | Cleared (Wilson) | GF fired / before face | First-A / take-off | Criterion | Result |
|---|---|---|---|---|---|
| real | 20/20 (84-100%) | 20/20 / 20 | A x median 404; take-off median 407 | >= 14 | pass |
| degree shuffle | 0/20 (0-16%) | 20/20 (landmark, x 321, theta 16, d 114) / 20 | A runs 13/20, all at x 321, taps 0 | <= 2 | pass |
| class shuffle | 0/20 | 0/20 | A 1 run | informative | uninformative here (0/20, no GF) |
| real_no_obstacle | 0/20, all stuck | 0/20 | no A | <= 2 | pass |
Context: step 3 E2a 20/20. Same.
Real GF, theta, d: theta 38.4-43.6 deg (median 43.6), surface d 40-46 px; GF 39-45 px before the stall point (14 of 20 at 39). First A 27-39 px before the stall point (median 30); take-off 24-36 px (median 27). A-run: 2 taps (1 frame), 18 holds of 11-15 frames, median 13.
Too early? Against the pipe-1 window for a 1-frame tap (5-29 px before stall): the GF fires 10-16 px EARLIER than the far edge of the window (39-45 vs 29), first A is at 27-39 (the far edge to 10 px beyond), take-off 24-36 (inside the window for 14 of 20, beyond it for 6). Against the long-hold window (35-65): all GF, first A and take-off lie at or just below its near edge (take-off 24-36, mostly 27, i.e. below 35), so a long hold started at this distance is slightly LATE relative to it, not early. The in-game take-off distribution sits on the boundary between the two windows. 18/20 are 11-15-frame holds.
The degree shuffle fires its GF at the face onset (landmark plus onset transient, theta 16) in 20/20 and still fails to clear 20/20: GF-fired is not a pass signal for the shuffle; clearing is.

## 3. B11 (seeds 6500-6519)
| Arm | max_x mean (CI), median | Ends |
|---|---|---|
| real | 698 (653-756), 722 | died_enemy 2, died_pit 1, stuck 17; none reached the goal |
| degree shuffle | 40 (40-40), 40 | stuck 20 |
| class shuffle | 40 (40-40), 40 | stuck 20 |
Real: stall/death x: 8 stuck at 596 (pipe 2), 9 stuck at 722-723 (pipe 3), 1 died at 723, 1 died at 844, 1 died at 1128 (pit). Pipe 1 cleared 20/20, pipe 2 cleared 12/20, pipe 3 cleared 2/20 (844 and 1128). Goombas jumped/encountered 34/35; 0 of 20 died at the first Goomba. Taps (1-frame A runs) 12 of 111 runs in 11 episodes; whole-episode tap episodes 0/20; A-run histogram 1:12, 2:6, 3-5:7, 6-10:3, 11+:83. Power-up released 0/20, collected 0/20. GF first spike frame 102 in all 20 (first Goomba at x about 303). Seed 9200 (same Goomba): GF at surface d 12, theta 45.2 deg, 3-4 frames before contact; GF fires in 20/20 real. Shuffles: GF fires from the landmark onset, mario never leaves x 40.
Context: step 3 B11 (6400-6419): mean 385, 15 died at the Goomba, 5 stalled at pipe 2 x 596. Now: mean 698. BETTER (different seeds).

## 4. Dose-response (seeds 6600-6619, real and degree shuffle; the CLI has no class-shuffle arm)
| GOAL_CUE_SALIENCE | real speed | survived first Goomba / 20 | max_x mean (CI) | pipe 1 | shuffled speed / survived |
|---|---|---|---|---|---|
| 5 | 2.547 | 5 | 416 (340-513) | 5/20 | -0.400 / 0 |
| 8 | 2.569 | 19 | 656 (594-724) | 19/20 | -0.400 / 0 |
| 11 | 2.570 | 20 | 666 (615-730) | 20/20 | -0.400 / 0 |
| 15 | 2.570 | 20 | 647 (615-680) | 20/20 | -0.400 / 0 |
Previous (6200-6219): survival 1/10/9/8, speed 2.545/2.57/2.57/2.57. Same speed curve (flat above 8); survival at the first Goomba higher at every value (5 / 19 / 20 / 20 of 20 vs 1/10/9/8 -- the earlier counts may have been of a different denominator, 20 per value in the log; stated as recorded).

## 5. Tests
Root tests/: 295 collected, 295 passed, 0 failed, 0 skipped (three disjoint file chunks, 100 + 95 + 100; golden test passed). tool/tests/test_brain_tool.py: 17 passed.

## Verdict
- E1: WORSE (real 10/20 misses the >= 16 criterion; class 15/20; degree 0/20 and lesion 0/20 pass). Deaths are short A presses (2-6 frames).
- E2a: SAME (20/20 vs 20/20; take-off 24-36 px before the stall point).
- B11: BETTER (mean 698 vs 385; no deaths at the first Goomba; stalls moved to pipe 2 (8) and pipe 3 (10)).
- Dose-response: BETTER on survival, SAME on speed.

Video: projects/redesign_e1/runs/228a_b11_real_seed9200.mp4 (seed 9200, stuck at pipe 3, x 722, 542 frames).

## Corrections and additions (2026-10-06, after review; append-only)

D1 dose-response reconciliation. Recomputed read-only from audit/p10_dose.json (seeds 6200-6219) and audit/p16_dose.json (seeds 6600-6619): both use the same field, `curve[v].real.first_goomba.survived` of `n` = 20 (died_enemy + survived = 20, unresolved 0, no_contact 0 in both). Definition and denominator therefore MATCH; the table in section 4 stands (previous 1/10/9/8, now 5/19/20/20). So the 20-point swing is real in the data but NOT attributable: the code changed (step 4) and the seed set changed (6200 vs 6600) together, and no run exists with the old code on the new seeds or the new code on the old seeds. "BETTER on survival" in section 4 and the Verdict should be read as "higher on different seeds, cause not separated from seed noise". The earlier hedge about "a different denominator" is withdrawn: the denominators are the same.

D3 additions to the verdict.
- (i) The step-3 B11 pipe-2 regression (docs/RESULTS_5c_step3.md section 4, "cause not diagnosed") was never diagnosed and recurs here: 8/20 real runs stall at x 596 (pipe 2); pipe 2 cleared 12/20.
- (ii) E1 real 10/20 (30-70%) is not distinguishable from class shuffle 15/20 (53-89%): the CIs overlap. E1 therefore does not show that specific wiring matters for the escape jump.
- (iii) The B11 698-vs-385 comparison is across different seed sets (6500-6519 vs 6400-6419) and different code; the gain comes from first-Goomba survival (15/20 deaths -> 0/20), after which stalls move to pipes 2 and 3. Seed noise applies, and B11 real is near-deterministic (few distinct trajectories).
- Scope of the enemy hitbox (w 10, left 3): measured for Goomba (presumed Koopa) only; not valid for other enemy kinds. 1-1 is unaffected. Elevation still uses sprite centres (open item, step 5 candidate).
