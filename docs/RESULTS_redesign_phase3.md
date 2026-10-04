# Phase 3 results (experimenter, 2026-10-04)

Network 3848f3e70b2051ef (16,464 neurons, 612,566 non-zero edges), calibration 9cf9317984a0b28c. Every measurement run once, no parameter changed. Raw outputs: audit/p3_*.txt, audit/p3_e0.json, p3_e3.json, p3_e1.json.

## 1. Phase 1 gates on the new network (`python -m audit.p1_disc`, network-generic via load_or_build)

| test | real | shuffled 1-5 | criterion | result |
|---|---|---|---|---|
| disc GF angle l/v 10/20/40/80 | 47.2 / 47.2 / 47.2 / 40.6 deg | no fire (all 4 l/v, all 5) | 38-48, spread <= 8, shuffles no fire | PASS (spread 6.6) |
| rest GF spikes | 0 | 0 (all 5) | 0 | PASS |
| rest max/threshold walk, back, steer | 0.83, 0.83, 0.82 | walk 0.88-0.94, back 0.85-0.92, steer 0.81-0.86 | report only (< 1) | all < 1 |

(Phase 2 network: real rest ratios 0.73/0.77/0.85, disc 47.2/47.2/40.6/43.6.)

## 2. Synthetic pre-game checks (audit/p3_synth.py; tests' own helper `_disc_with`)

| condition | real | shuffled 1-5 | criterion | result |
|---|---|---|---|---|
| disc + landmark, l/v 10/20/40/80 | 47.2 / 47.2 / 47.2 / 40.6 | GF fires at 2.0-2.1 deg (first frame) in all 5 | 38-48, spread <= 8 | real PASS |
| disc + pursuit dead ahead, full arousal | 47.2 / 47.2 / 47.2 / 43.6 | fires at 2.0-2.1 deg in all 5 | same | real PASS |
| disc + landmark + pursuit | 47.2 / 47.2 / 47.2 / 40.6 | fires at 2.0-2.1 deg in all 5 | same | real PASS |
| rest, mechanisms attached, no cue | 5 seeds x 3000 frames: 0 GF spikes, 0 presses | 1 seed x 3000: 0 GF spikes, 1 press after frame 100 in each of the 5 shuffles | 0 / 0 | real PASS; shuffles report |
| after 100-frame cue removed | 0 presses from frame 40 on | 0 | none | PASS |

Shuffled GF fires immediately because the degree-shuffled wiring carries the added LC10a drive to the GF; this is the control's behaviour, not the fly's.

## 3. E0 walk to the goal (seeds 4000-4019, once; scene e0_walk_goal 27a671e7e27469e6)

| arm | reached | Wilson 95% | timeouts | deaths | median frames | GF crossed | GF out max Hz | TTMn max Hz | A / B / Left / Right (frame share) |
|---|---|---|---|---|---|---|---|---|---|
| real | 20/20 | 84-100% | 0 | 0 | 135 | 0/20 | 0.00 | 0.012 | 0 / 1.00 / 0 / 1.00 |
| shuffled | 0/20 | 0-16% | 20 | 0 | none | 20/20 | 12.00 | 0.777 | 0.016 / 1.00 / 1.00 / 0 |
| shuffled_class | 0/20 | 0-16% | 20 | 0 | none | 0/20 | 0.00 | 0.102 | 0.000 / 1.00 / 0.994 / 0.006 |

Criterion real >= 18, shuffled <= 2: PASS.

## 4. E3 pursue the mushroom (seeds 5000-5019, once; scene e3_mushroom cbde4f133a0f0870, bound 150 frames)

| arm | reached | Wilson 95% | timeouts | deaths | median frames | GF crossed | GF out max Hz | TTMn max Hz | A / B / Left / Right |
|---|---|---|---|---|---|---|---|---|---|
| real | 20/20 | 84-100% | 0 | 0 | 104 (102-105) | 0/20 | 0.00 | 0.012 | 0 / 0.38 / 0 / 0.42 |
| shuffled | 0/20 | 0-16% | 20 | 0 | none | 20/20 | 12.00 | 0.826 | 0.08 / 0.71 / 0.73 / 0.001 |
| shuffled_class | 0/20 | 0-16% | 20 | 0 | none | 0/20 | 0.00 | 0.104 | 0 / 0.66 / 0.58 / 0.08 |

Criterion real >= 14, shuffled <= 2: PASS. Passive-Mario baseline (SPEC section 6: presses nothing): fails both E0 and E3 in time (tests/test_phase3.py test passed; mushroom reaches a still Mario at frame 183 > 150).

## 5. E1 regression on the changed network (seeds 3000-3019; these seeds were used on the previous network; NOT a fresh held-out result)

| arm | survived | Wilson 95% | deaths | timeouts | GF before contact | A-press runs | GF out max Hz | TTMn max Hz | theta at GF |
|---|---|---|---|---|---|---|---|---|---|
| real | 13/20 | 43-82% | 7 | 0 | 20/20 | 20/20 | 15.00 | 0.355 | median 41.7 (40.0-43.6) |
| shuffled | 0/20 | 0-16% | 20 | 0 | 0/20 | 0/20 | 0.00 | 0.067 | none |
| lesion_gf | 0/20 | 0-16% | 20 | 0 | 20/20 | 0/20 | 0.00 | 0.011 | median 41.7 |

Phase 2 criterion real >= 16: **FAIL on this network** (Phase 2 network: 18/20). Same GF behaviour (20/20 before contact, same angles) but A holds are shorter: died seeds 3001, 3003, 3004, 3008, 3009, 3013, 3018 had A held 9, 7, 7, 5, 9, 9, 4 frames; survivors 11-20 (previous network: 18 survivors held 12-26, deaths held 3-4). Press rates per frame (E1 json stores A only): A 6.7% real.

**Caveat on the E1 line above (stated plainly).** 18/20 belongs to the Phase 2 network (hash `4736dc554136ac98`); on this network (`3848f3e70b2051ef`) real is 13/20 and the criterion >= 16 fails, on previously used seeds (not fresh held-out). GF fires before contact in 20/20; deaths held A 4-9 frames, survivors 11-20. Cause not diagnosed (correlation only).

**Footnotes.** E0 real is one deterministic trajectory (frame 135 on all 20 seeds), so its Wilson CI overstates independence. LC10A_AZIMUTH_SPLIT = 90 was a non-discriminating pick (all candidates passed). Rule-before-run provenance: see docs/SPEC_phase3.md section 10(e); ordering is unverifiable from artefacts, the values match the rules applied to the printed windows.

## 6. Tests (.venv, once)

tests/test_phase3.py, test_e1.py, test_brain_core.py, test_scalars_doc.py, tool/tests/test_brain_tool.py: 77 passed in 148 s.

## 7. Videos (seed 9200, project redesign_e1)

214a E0 real (reached frame 135), 214b E0 shuffled (timeout, Left 600/600, GF crossed), 215a E3 real (reached frame 105), 215b E3 shuffled (timeout, Left 112/150, GF crossed). docs/RUNS.md entries 214 and 215.

## Oddities
- E0 real reaches at frame 135 for all 20 noise seeds: the real arm is effectively deterministic, so 20/20 is one trajectory, not 20 independent ones.
- Shuffled arms hold Left (and B) the whole time; the cue drives the shuffled network's MDN. The degree shuffle's GF also fires 20/20 under the cue (12 Hz); the class shuffle never fires.
- E3 has no pursuit-off arm: the pass does not show pursuit is necessary (real moves right 42% of frames, B 38%). E0's landmark makes the "goal on the right" an input, not a discovery.
- E1 real fell 18 -> 13/20 with the LC10a addition (shorter A holds); real rest margins rose 0.73-0.85 -> 0.82-0.83.

## Full root tests (review fix F3)

Full root `tests/` run once in 3 chunks after the review fixes, goldens included (test_golden.py): 261 passed (119 + 99 + 43), 0 failed. tool/tests/test_brain_tool.py: 14 passed.

## Round 2 (decisions of 2026-10-04; earlier sections above are kept as history)

- Arousal no longer reads the fly's DNp09 (that was an invented feedback loop). It is the fly-state setting `PURSUIT_AROUSAL` (tool, Mechanisms tab), default 0.65 = midpoint of the window 0.3-1.0 found on the synthetic dot (docs/SPEC_phase3.md section 11, docs/senses_arousal_output.txt). Disc with pursuit + landmark on: GF 47.2 / 47.2 / 47.2 / 40.6 deg at 0.65 and at 1.0. The numbers above in sections 3-5 were produced with the old arousal; the experimenter reruns.
- Necessity arms added (eval only, labelled control): E0 `real_no_landmark`, E3 `real_no_pursuit`. E3 held-out seeds moved to 5100-5119 (5000-5019 are spent). Seed 9100 smoke: both necessity arms time out with no key pressed.
- E0 20/20 is one deterministic trajectory, not 20 independent successes. LC10A_AZIMUTH_SPLIT = 90 is the left/right eye boundary and was not selected by the data (all candidates passed). All E0 / E3 constants stay invented.

## Round 2 results (fresh seeds)

Each run once, network 3848f3e70b2051ef, calibration 9cf9317984a0b28c. Wilson 95% CI. Raw JSON: audit/p3r2_e1.json, audit/p3r2_e3.json, audit/p3r2_e0_nolandmark.json. Run 216 in docs/RUNS.md.

| Exp | Arm | Success | CI | Timeouts | Deaths | GF crossed | GF out max Hz | TTMn max Hz | Criterion | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 3100-3119 | real | 12/20 | 39-78% | 0 | 8 | 20/20 | 12.0 | 0.32 | >= 16 | FAIL |
| E1 | shuffled | 0/20 | 0-16% | 0 | 20 | 0/20 | 0.0 | 0.07 | <= 2 | pass |
| E1 | shuffled_class | 13/20 | 43-82% | 0 | 7 | 20/20 | 18.0 | 0.49 | (reported) | n/a: E1 class-shuffled 13/20 vs real 12/20 on fresh seeds, near-equal with overlapping CIs, so E1 survival does not separate real from class-preserving wiring |
| E1 | lesion_gf (control) | 0/20 | 0-16% | 0 | 20 | 20/20 | 0.0 | 0.01 | should fail | fails as expected |
| E3 5100-5119 | real (median 105.5 frames) | 20/20 | 84-100% | 0 | 0 | 0/20 | 0.0 | 0.01 | >= 14 | pass |
| E3 | shuffled | 0/20 | 0-16% | 20 | 0 | 15/20 | 9.0 | 0.54 | <= 2 | pass |
| E3 | shuffled_class | 3/20 (median 104) | 5-36% | 17 | 0 | 0/20 | 0.0 | 0.07 | <= 2 | FAIL (3) |
| E3 | real_no_pursuit (control) | 0/20 | 0-16% | 20 | 0 | 0/20 | 0.0 | 0.01 | should fail | fails as expected |
| E0 4000-4019 | real_no_landmark (control) | 0/20 | 0-16% | 20 | 0 | 0/20 | 0.0 | 0.01 | should fail | fails as expected |

E0 real / shuffled / shuffled_class were not rerun (unaffected by the arousal change; earlier single run stands). Per-key A/B/Left/Right rates are not stored in the eval JSON except mean Left frames (E3: real 0, shuffled 110, shuffled_class 71.3, no_pursuit 0; max x median 409 / 330 / 334.5 / 330). E1 real A-press runs 20/20; E1 median frames not stored. E1 new-network baseline: real 12/20 < 16, so the criterion is not met on fresh seeds; the 13/20 on reused seeds 3000-3019 was a regression check and is consistent with it. tests/test_phase3.py: 27 passed.

## Round 2 corrections (reviewer, 2026-10-04; history above kept)

- E3 class-shuffle control FAILED on fresh seeds 5100-5119: 3/20 (CI 5-36%) vs criterion <= 2. E1 fresh-seed real 12/20 FAILS >= 16; E1 class-shuffled 13/20, so E1 survival does not separate real from class-preserving wiring (12 vs 13/20, overlapping CIs). Entries 214/215 used the DNp09-arousal rule and are superseded for E3 (class-shuffle 0/20 -> 3/20); that E0 real/shuffled are unaffected is plausible, not rerun. docs/RUNS.md entry 217.
- E0's necessity result (real_no_landmark 0/20) stands beside "E0 is one deterministic trajectory" (frame 135 on every seed); E3 real is near-deterministic (median 105.5, frames 102-106).
- The E1 diagnosis (shorter A holds) is correlational: brain-only evidence, not a paired closed-loop test. 12/20 on fresh seeds matching 13/20 on replayed seeds supports "not seed luck".
- Rule-before-run ordering of PURSUIT_AROUSAL is unverifiable from artefacts (mtimes: calibration.py 13:50:31, senses_arousal_output.txt 13:50:41, SPEC 13:55:17); 0.65 equals the midpoint of the stated 0.3-1.0 window.
- Videos: 216b is the no-pursuit control; there is no shuffled video for 216 and no E1 video for the 12/20 result.
