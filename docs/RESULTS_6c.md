# Phase 6c Part 1 validation: expansion gate (2026-10-07)

Measure only: no repo code or config edited. Gate = LPLC2 size channel carries theta only while dtheta > 0 and previous theta > 0 (docs/SPEC_geometry_5c.md Step 7). Scratch scripts: audit/p22_*.py. Raw: audit/p22_{e1,e2a,b11}.json, audit/p22_b11_real_logged.json, audit/p22_shadow.txt. Each eval run once, fresh seeds, 8 workers. Network 3848f3e70b2051ef, calibration 343d8f60abcdba25 (unchanged).
E0 not run: it uses neither the looming nor the obstacle-expansion channel (no Goomba, no obstacle; pursuit/landmark only), so the gate cannot change its input (provable no-op).

## E1 (seeds 3600-3619) vs previous round (3500)
| arm | now | previous (3500) | criterion | result |
|---|---|---|---|---|
| real | 19/20 (Wilson 76-99%); 19 stomped, 1 died | 13/20 | >= 16/20 | pass |
| degree shuffle | 0/20 (0-16%) | 0/20 | <= 4/20 | pass |
| class shuffle | 12/20 (39-78%) | 14/20 | informative | n/a |
| GF lesion | 0/20 | 0/20 | informative | n/a |

Real: GF before contact 20/20 at d 12 px in all 20 (previous 12-14), theta 45.2 deg in all 20 (previous 39-45); frames from first GF to contact median 27 (range 14-30; previous 19.5, 14-30). A frames per run median 15 (range 4-19); the one death (3618) had 4 A frames (lead 15); 3614 had 9 A frames (lead 14) and survived. Previous round: 7 deaths, A frames 2-6 in all 7. Degree shuffle: GF never fires. Class shuffle: GF fires 20/20 at median d 14 px, 8 died.

E1 real vs class, pooled over independent fresh sets: 3200 16 v 16; 3300 10 v 15; 3400 13 v 16; 3500 13 v 14; 3600 19 v 12. Pooled 5 sets: real 71/100 vs class 73/100, Fisher p = 0.87. Set 3600 alone (first set with the gate): real 19/20 vs class 12/20, Fisher p = 0.020. Real 3600 vs real 3500: 19/20 vs 13/20, p = 0.044. The gate changed the stimulus layer between 3500 and 3600, so sets 3200-3500 (real 52/80, class 61/80, p = 0.165) and 3600 are different populations; one gated set is not enough to say the class shuffle is now beaten.

## E2a (seeds 7600-7619)
| arm | now | previous (7500) | criterion | result |
|---|---|---|---|---|
| real | 18/20 (70-97%); 2 stuck at x 436 | 20/20 | >= 14/20 | pass |
| degree shuffle | 0/20 | 0/20 | <= 2/20 | pass |
| class shuffle | 0/20 | 0/20 | informative | n/a |
| no obstacle | 0/20 | 0/20 | <= 2/20 | pass |

Real: GF 20/20 before the face, GF at d median 40 px (40-46), theta 43.6 deg median (38-44), x median 395; first A x median 401 (395-407), take-off x median 404 (398-410); taps 3/20 (seeds 7603, 7613, 7619); the two stuck runs (7603, 7613) are tap-first-A episodes that stopped at x 436 and timed out (353 frames). Previous: 5 taps, all cleared. 20/20 vs 18/20 Fisher p = 0.49 (not distinguishable).

## B11 (seeds 6900-6919) vs previous (6800)
| measure | now | previous |
|---|---|---|
| max_x mean (bootstrap 95% CI) | 620 (588-649) | 673 (628-738) |
| median | 596 | 596 |
| ends | 19 stuck, 1 died_enemy | 14 stuck, 5 died_enemy, 1 died_pit |
| stalls by x | 596: 14; 722: 4; 437: 1 | 596: 12; 722: 2 |
| deaths | 1 (seed 6914, x 722, frame 270) | 6 (4 at 722, 852, 1129) |
| pipes cleared 1/2/3 (max_x > 480/600/725) | 19 / 5 / 0 | 20 / 8 / 2 |
| Goombas jumped | 25/25 | not tabulated |
| first-Goomba deaths (died before x 500) | 0 | 0 (the 5 enemy deaths were at x 722-852) |
| A runs (1 / 2 / 3-5 / 6-10 / 11+) | 11 / 4 / 7 / 1 / 65 | 21 / 4 / 3 / 5 / 76 |
| A-tap episodes | 0/20 | 0/20 |
| GF output max, TTMn max | 18 Hz, 0.443 Hz | 18 Hz, 0.455 Hz |
| shuffles | degree 20/20 stuck at x 40; class 20/20 stuck at x 40 | same |

Mean max_x is lower than last round (620 vs 673), pipe 2 cleared 5/20 vs 8/20, pipe 3 cleared 0 vs 2: nominally worse, within seed noise (CIs overlap). Deaths fell 6 -> 1.

## Wall stall: does the latch survive the gate?
Read-only logger replay of the same 20 B11 real episodes (audit/p22_b11_real_logged.json; reproduces the eval exactly: max_x and frames equal in 20/20). Last 100 frames of stalled episodes:

| measure | previous round (RUNS 229, seeds 9300-9319) | now (6900-6919) |
|---|---|---|
| stalled episodes | 17 | 19 |
| GF fires every frame | 17/17 (100 of 100 frames) | 0/19 (0 of 100 frames in all 19) |
| TTMn median | 0.474 | 0.007 (min 0.002) |
| A held 100% / 0% / mixed | 2 / 14 / 1 | 0 / 19 / 0 |

(RUNS 230 recorded 15/15 at 100/100 GF frames for a 15-episode subset.) The latch is gone. Mario does not become unstuck, though: stalls remain at x 594 (14), 722 (4) and 434-437 (1). Timeline in the 19 stalled episodes: GF fires on 20-26 of the 30 frames before Mario's x reaches its final value (9 at seed 6908, pipe 1), A is pressed 13-26 of those 30 frames (a jump attempt), then GF fires 3-6 more frames after arrival and goes silent; A is off for the rest of the episode. So the circuit approaches the pipe as an expanding object, tries a jump that does not clear it, and then the static wall gives dtheta = 0, the gate drops theta to 0, nothing fires, and Mario walks into the wall forever. Why the jump does not clear pipe 2/3 (while pipe 1 is cleared in E2a at a similar approach) was not investigated.

## Did the gate hurt?
Goomba escape: 25/25 Goombas jumped in B11 and 0 first-Goomba deaths; E1 survival rose 13/20 -> 19/20 and the GF-to-contact lead rose 19.5 -> 27 frames median. The implementer's reading (GF at d 13 -> 10 in 2 of 3 seeds) is not seen in E1: d at first GF is 12 px in all 20 seeds. E2a lost 2 runs (taps stuck at 436, p = 0.49).

## Verdict
- E1: better (19/20 vs 13/20; criterion met; against the class shuffle better in this set, not pooled).
- E2a: same (18/20 vs 20/20, within noise).
- B11: same to slightly worse on max_x (620 vs 673, pipes 19/5/0 vs 20/8/2), fewer deaths (1 vs 6).
- Wall stall: latch removed (GF silent on 100% of stalled frames), stall itself not removed (19/20 still stuck at pipes).

## Tests
`pytest -m fast` from the repo root fails at collection (70 errors, "import file mismatch": audit/old_code/tests duplicates of tests/ basenames; no tests ran, 27 s). `pytest -m fast tests`: 13 passed, 303 deselected, 144 s.
Video: projects/redesign_e1/runs/231a_b11_real_seed9200.mp4 (seed 9200 stuck at x 437 at pipe 1, 447 frames; one seed is an observation).
