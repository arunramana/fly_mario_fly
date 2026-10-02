# Phase 1 (brain core) validation results, 2026-10-01

Network 4736dc554136ac98 (15,551 neurons; 592,683 built edges, 568,527 non-zero weights; shuffles 556.6-556.7k non-zero weights), calibration.json unchanged
(g 0.85, gf_threshold 0.1680). Nothing tuned on game outcomes; calibration, model and network are unchanged since the first run.
Scripts: audit/p1_disc.py, audit/p1_e1.py, audit/p1_e1_diag.py (old proxy, superseded); raw old proxy output audit/e1_20seeds.json.
After fix round 1 the checks were re-run: audit/p1r2_disc.txt (disc and rest), audit/p1r2_ground.txt (ground object),
audit/p1r2_eval.json (standard eval). Summary: the disc gate passes; **the Phase 1 eval gate (real >= 16/20) was NOT TESTABLE, not failed
(0/20 real, 0/20 shuffled)**: with no goal cue Mario has no locomotion, so the first Goomba is never reached (details below).
Arun accepted this as "wired, run, not testable"; the real E1 scene (action-log savestate, Goomba walking toward a stationary Mario)
is the start of Phase 2.

## tests/test_brain_core.py
23 passed (18 in the original run under system python; 5 added in fix round 1). Fix round 1: environment fixed (scipy 1.13.1 and numpy 1.26.4 in the repo .venv, recorded in requirements.txt); see the fix-round section at the end.

## Full root tests/ (CLAUDE.md: changes outside tool/)
Run in the repo .venv (`.venv/Scripts/python.exe -m pytest tests/ ...`), split into 8 parallel pytest invocations because a single serial
run timed out at 30 minutes. Chunk results: 26 + 23 + 23 + 44 + 36 + 37 + 16 + 17 = **222 passed, 0 failed**, including `test_golden.py`
(goldens unchanged) and the scalars-doc test. Reported by the implementer; the per-chunk file split was not recorded.

## Disc (GF firing angle, deg) and rest
Gate (docs/SPEC_brain_core.md). Note: the gate was widened from the original 41-47 deg window to 38-48 deg AFTER the first result (l/v 40 gave 40.6, 0.4 deg outside), with Arun's approval; margins against the new gate are thin: max 47.2 vs 48 deg, spread 6.6 vs 8 deg. The calibration (40 deg target) was not changed. Gate: real fires at 38-48 deg for every l/v, spread <= 8 deg; shuffled do not fire.
| l/v ms | real | shuffled 1-5 | criterion | result |
|---|---|---|---|---|
| 10 | 47.2 | no fire x5 | 38-48 real | pass |
| 20 | 47.2 | no fire x5 | 38-48 real | pass |
| 40 | 40.6 | no fire x5 | 38-48 real | pass |
| 80 | 43.6 | no fire x5 | 38-48 real | pass |
| spread (max - min) | 6.6 | - | <= 8 | pass |
| rest GF spikes (2000 frames, seed 0) | 0 | 0 x5 | 0 | pass |
| rest max walk/steer/back (thr .0171/.0109/.0139) | .0124/.0093/.0107 | max .0142/.0100/.0120 | below thr | pass |

Known risk (reported, not re-tuned): the shuffled rest maximum is within about 8% (steer: .0100 vs .0109) and 14% (back: .0120 vs .0139)
of the thresholds, so a motor false positive at rest on a shuffled brain is possible. The real brain is 15-27% below.

Re-run after fix round 1 (audit/p1r2_disc.txt): identical firing angles; rest max/threshold for the real brain walk 0.73, back 0.77,
steer 0.85; shuffled 1-5 between 0.78 and 0.91, the highest being shuffle 4 steer at 0.91 (never reached 1.0, no GF rest spikes).

## Ground-level object (synthetic, audit/p1r2_ground.txt)
Same-level Goomba vs small Mario, new elevation encoding: theta 39.97 / 29.86 / 20.16 / 13.04 / 7.63 deg at d = 22 / 30 / 45 / 70 / 120 px
(= 2 atan(8/d), weight 1). Approach at 0.5 / 1 / 2 px per frame: real GF first fires at 40.0 / 43.6 / 40.0 deg; the 5 shuffles never fire.

## E1
Not tested. The earlier proxy (1-1 scripted walk to the first Goomba, then BrainPolicy with no goal cue, 0/20 survived for both arms)
is not an E1 result: no E1 scene exists in the repo (it is Phase 2), the proxy had no drive, and it exposed defect D1 (elevation
encoding, below), which made theta peak at only ~30 deg. Those numbers are not used as evidence either way.

## Standard eval (20 seeds, real vs shuffled), audit/p1r2_eval.json
`python -m scripts.eval_brain`: 1-1, seeds 2000-2019, 1500 frames max, metric "past the first Goomba".
| arm | past first Goomba | Wilson 95% CI | deaths | GF spikes | A presses |
|---|---|---|---|---|---|
| real | 0/20 | 0-16.1% | 0 | 0 | 0 |
| shuffled | 0/20 | 0-16.1% | 0 | 0 | 0 |

Every episode ended at 1500 frames with max_x = 40 and goomba_x = None: Mario never walked, so the first Goomba was never seen and
the metric could not be met. **The gate (real >= 16/20) was not testable, not failed.** Cause: Phase 1 has no goal cue (D2, Phase 3) so the fly stands;
the metric cannot discriminate in Phase 1. This is not evidence about the looming circuit (see the disc and ground-object results).

## Edge counts and unknown-transmitter neurons
592,683 built edges (the rule's edges, as Phase 0 expected) and 568,527 non-zero weights. The difference, 24,156 edges, is the outgoing
connections of the 430 neurons with unknown predicted transmitter (sign 0, dropped as sources, Dale's law). None of the 430 is an output
neuron (GF, TTMn, DNp09, DNa01/02, MDN) or an LC4/LPLC2 neuron. 13 are head GRNs (sensory, not yet driven by any mechanism) and 2 are
DANs. Both counts are in every `Brain.stamp()`.

## Fix round 1 (2026-10-01)
- Disc gate rewritten (above); calibration unchanged (g 0.85, gf_threshold 0.1680, 40 deg target).
- Defect D1 fixed in brain/perception.py (centres instead of raw Y bytes); validated on a synthetic ground-level object only.
- Brain scalar registry brain/scalars.py -> docs/SCALARS_BRAIN.md (generated); config/params.py untouched.
- Scalar registry: 25 scalars = 18 invented + 6 calibrated + 1 measured (docs/SCALARS_BRAIN.md; CLIP_HZ re-tagged invented in round 2,
  its citation only supports an order of magnitude; "measured" here means literature or data, unlike the legacy meaning).
- Sprite geometry (16 px sprite, 8 px Y-byte offset) is validated for small Mario vs a Goomba on flat ground only; re-validate in Phase 2
  before Koopas.
- Environment: scipy 1.13.1 added to the repo .venv, numpy 1.26.4 kept (nes_py needs numpy<2); requirements.txt updated; no sys.path hacks.
