# RESULTS: walking-speed dose-response (SPEC_dose_response.md)

This is a dose-response, not tuning. No value is adopted; the registry default GOAL_CUE_SALIENCE stays 15. One run, no retries. Raw: audit/p10_dose.json (41 min, 4 workers, seeds 6200-6219 for every value).

## Real arm

| value | speed px/f mean (CI) | contact frame (mean) | contact x (mean) | first Goomba surv/died/unres/no_contact | jumped/enc | max_x mean (CI) | median | pipe1 cleared | tap frac | end reasons | distinct outcomes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 2.545 (2.540-2.549) | 103.8 | 306 | 1/19/0/0 | 2/21 | 333 (312-374) | 312 | 1/20 | 0.45 | {'died_enemy': 19, 'stuck': 1} | 3 |
| 8 | 2.570 (2.570-2.570) | 103.0 | 306 | 10/10/0/0 | 20/32 | 528 (437-621) | 518 | 10/20 | 0.0 | {'died_enemy': 12, 'stuck': 8} | 10 |
| 11 | 2.570 (2.570-2.570) | 103.0 | 306 | 9/11/0/0 | 18/31 | 505 (417-596) | 315 | 9/20 | 0.0 | {'died_enemy': 13, 'stuck': 7} | 8 |
| 15 | 2.570 (2.570-2.570) | 103.0 | 306 | 8/12/0/0 | 16/28 | 466 (384-552) | 315 | 7/20 | 0.0 | {'died_enemy': 13, 'stuck': 7} | 9 |

## Shuffled arm (degree-preserving, shuffle seed 1+i)

| value | max_x | end reasons | Goomba contacts |
|---|---|---|---|
| 5 | 40 (all 40) | {'stuck': 20} | 0/20 |
| 8 | 40 (all 40) | {'stuck': 20} | 0/20 |
| 11 | 40 (all 40) | {'stuck': 20} | 0/20 |
| 15 | 40 (all 40) | {'stuck': 20} | 0/20 |

All 80 shuffled episodes: max_x 40, ended `stuck` at frame 301; speed -0.4 px/frame; never walked right, never met a Goomba.

## Reading (measured, not interpreted as tuning)
- Speed to frame 100 is flat: 2.545 at 5, 2.570 at 8, 11 and 15 (a 0.025 px/frame difference, about 1%). Contact frame 103-104 and contact x 306 are the same at every value. The dose does not change when or where the first Goomba is reached.
- Survival at the first Goomba (real, n=20): 1 (5), 10 (8), 9 (11), 8 (15). Not monotone: a jump from 1 to 10 between 5 and 8, then 10, 9, 8 (a drift of 1 per step, well inside noise, Wilson CIs wide). The only step that is large is 5 to 8; the 5 episodes differ by A-tap behaviour (9/20 tapped, 0/20 at the other values; all 20 pressed A, taps do not make the jump).
- max_x: mean 333, 528, 505, 466; medians 312, 518, 315, 315. Driven by survivors (stall at x 722-723, a few at 899-900 or 594/679/434); not monotone above 8.
- Trajectory count: value 5 has 3 distinct (outcome, max_x, frames) outcomes, 8 has 10, 11 has 8, 15 has 9; in every value the majority is the identical died_enemy at x 312-315, frame 106, so the death mode is near-deterministic while the survivors vary.
- The previous registry-default runs (RUNS 221/224) gave 7/20 and 5/20 surviving; value 15 here gives 8/20 on fresh seeds, consistent.
