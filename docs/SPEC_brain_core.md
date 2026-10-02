# SPEC: brain core (redesign phase 1)

Scope: `docs/REDESIGN_PLAN.md` section 7, phase 1, and nothing else. New package `brain/`; the legacy path (`bridge/full_policy.py`,
`fly/circuits/`, `run_steering.py`, `config/params.py`, their tests and goldens) is not edited. No goal cue (D2, Phase 3), no gaps
(E5 / D3), no smell/taste/pain mechanisms: their sensory populations are in the manifest so the network contains their routes, but
nothing drives them yet.

**Disc gate (fixed before any re-run; supersedes the earlier 41-47 deg parity window).** Real GF fires at 38-48 deg for every l/v in
10, 20, 40, 80 ms (and the whole 10..80 ms range), with a spread (max - min over those speeds) of at most 8 deg; the shuffled
networks (5 seeds, same fixed numbers) do not fire. The calibration target stays 40 deg (Ache et al. 2019): the numbers are not
re-calibrated to chase tenths of a degree.

**The rule.** Stimuli enter only at sensory-tier neurons listed in the manifest. No code path adds current to any other neuron; no
dopamine injection. The motor map only reads. Its thresholds come from synthetic tests and are not experiment inputs. Nothing is tuned
on game outcomes: a value is derived, validated on the disc or the rest test, and stops there.

## 1. Files (plan section 6)

| File | Status | Role |
|---|---|---|
| `brain/manifest.py` | new | sensory tier, outputs, mushroom body, path segments, fixed motor table, k and N |
| `brain/builder.py` | new, reuses `mcns` and `fly/connectome/circuit.py` | streams weights once, path-union, sparse signed weights, shuffled twin, save/load |
| `brain/calibration.py`, `brain/calibration.json` | new | constants with provenance; derived numbers tied to a network hash |
| `brain/calibrate.py` | new | derivation CLI (gain, GF threshold, motor thresholds) plus real-vs-shuffled disc report |
| `brain/brain.py` | new, reuses `fly/network/{integrator,network,dynamics}.py` | sensory-only stimulus API, frame step, stamp |
| `brain/mechanisms.py` | new | `Stimulus`, `LoomingMechanism` (ported from `bridge/loom_disc.py` encoding) |
| `brain/disc.py` | new, reuses constants of `bridge/loom_disc.py` | disc and rest bench for `Brain` |
| `brain/motor_map.py` | new | read-only buttons from output neurons |
| `brain/policy.py` | new, ~70 lines | `sim.protocols.Policy`; scene from `brain/perception.py` (visible enemies only) |
| `brain/perception.py` | new (fix round 1) | enemy theta with the corrected elevation encoding (section 6); `bridge/perception.py` stays frozen |
| `brain/scalars.py`, `docs/SCALARS_BRAIN.md` | new (fix round 1) | the brain's scalar registry (measured / calibrated / invented); the doc is generated from it |
| `brain/evaluation.py`, `scripts/eval_brain.py` | new (fix round 1) | standard eval wired to `BrainPolicy` (section 9) |
| `tests/test_brain_core.py` | new | tests below |

## 2. Manifest

Populations are selected from the annotations by class/type and their verified counts are asserted at resolve time.
Sensory tier: LC4 (126) and LPLC2 (185) (vision entry tier D1: early feature neurons, labelled so; photoreceptors are out of scope per
INVEST_phase0 2.1/4), plus ORN (2,639), head GRN (275) and thermosensory (25) which only have wiring for now. Outputs: GF = DNp01 (2),
TTMn (2), DNp09 (2), DNa01 (2), DNa02 (2), MDN (4). Mushroom body: Kenyon cells 4,064, MBON 97, DAN 340, always included whole.

Side comes from the `instance` suffix, then `rootSide`, then `somaSide` (sensory somas are in the periphery).

## 3. Network rule (INVEST_phase0 2.4 B, recommended)

k = 3 hops, N = 5 synapses. Segments, each "every neuron on a walk of <= k hops from sources to targets": vision -> outputs,
ORN -> KC, head GRN -> DAN, thermo -> DAN, MBON -> outputs; union of the segments plus every KC, MBON and DAN. Edges: all
connections of >= N synapses between selected neurons (both ends annotated bodies). Expected from Phase 0: 15,551 neurons, 592,683 edges.
The weights file is streamed once in Arrow record batches (`mcns._edge_batches`) and the reduced edge table cached under
`../data/derived/`; the file is never loaded whole.

Weights: `W[j, i] = sign_i * synapses_ij / (in-network input of j)`, sign from the predicted transmitter of the presynaptic neuron (Dale's
law, `circuit.NT_SIGN`; unknown transmitter -> sign 0, dropped as a source). This is the recipe of `circuit.build_weight_matrix`
(in-network, not whole-connectome, input as denominator; the plan text says "total input" but the verified recipe the plan points to
normalises by in-network input, and the GF threshold is calibrated on the result either way). Whole-connectome input is stored for
diagnostics. A test checks the sparse builder equals `circuit.build_weight_matrix` on a small subnet.

The rule, k, N, segment list and neuron/edge/population counts are saved with the brain (`BuiltNetwork.rule`, in the npz) and
stamped on every result with a build hash.

Shuffled twin: `circuit.shuffle_edges` (permute the post column over all edges: same neurons, signs, in- and out-degree), then the
identical normalisation, and the same calibration numbers.

## 4. Brain

One neuron model for every neuron: `h <- (1-alpha) h + alpha clip(g W h + I + eta, 0, 200 Hz)`, alpha 0.3, 10 substeps per frame;
only the GF (DNp01, 2 cells) is leaky-integrate-and-fire with a 3-substep refractory period (it spikes singly), spike amplitude 60 Hz.
`I` is private to `Brain`, written only by `stimulate`/`apply`, which raise `StimulusError` for any id outside the manifest's sensory tier
and add nothing. `eta` is each neuron's own membrane noise (sigma 0.015, same as the calibrated path), not an input.

One gain: `g = min(1.0, 0.85 / rho(W))` (rho by sparse eigensolve), the same g for the shuffled twin.

## 5. Calibration (synthetic only), `python -m brain.calibrate`

| Number | Derivation | Kind |
|---|---|---|
| `g` | spectral-radius criterion above | derived |
| `gf_threshold` | mean over discs l/v 20/40/80 of the GF membrane at theta = 40 deg, spiking disabled (target: Ache et al. 2019, verified in SPEC_bio_calibration) | measured |
| `walk`, `steer`, `back` thresholds | rest run (no stimulus, noise only, 2 seeds x 1500 frames): mean + 6 std of the pooled activity of DNp09, |left - right| DNa01/02, MDN; floor 1e-3 Hz | measured; the 6 is an invented convention |
| `a_threshold` | 0.5 x the weakest calibration disc's peak A-muscle drive | measured; the 0.5 is an invented convention |
| `muscle_decay` | 0.9 per frame (tau ~10 frames), same as `MotorDirectParams.decay` | invented |

Fixed constants with provenance in `brain/calibration.py`: alpha, substeps, clip 200 Hz, spike 60 Hz, refractory 3, noise 0.015,
margin 0.85, G_NOMINAL 1.0, THETA_GF 40 deg (same values as the validated bio_strict path so the parity check is like for like).
Perception: `ELEVATION_LIMIT_DEG` 60 (invented, in `brain/calibration.py`; same value as the validated bio_strict path).
Every scalar above, the network rule (k, N), the elevation limit and the derived thresholds are listed with a kind tag
(measured / calibrated / invented) and a sanity range in `brain/scalars.py`; `python -m brain.scalars` generates
`docs/SCALARS_BRAIN.md` (never hand-written; a test checks it is current). `config/params.py` and `docs/SCALARS.md` are the legacy
registry and are not touched.
`calibration.json` stores the numbers and the build hash of the network they were derived on; `Brain` refuses a mismatch.

## 6. Looming mechanism

Cue: nearest visible enemy ahead, theta = 2 atan(w / 2|d|) with the elevation weighting of `bio_enemy_thetas`, but with the
elevation computed in `brain/perception.py` (defect D1). The frozen version compares the raw Player_Y_Position byte with the raw
Enemy_Y_Position byte, which sit on different baselines (1-1, small Mario on flat ground: player 176, Goomba 184, both with feet
at screen y 208), so a same-level Goomba read as ~30 deg elevation at close range and theta was down-weighted. The new code compares
vertical centres: Mario's centre = hitbox bottom (RAM 0x04AF) minus half his height (16/32 px by RAM 0x0756); an enemy's centre =
Y byte + 8 (sprite top) + 8 (half of the 16 px sprite the registry assumes). Validated only on a synthetic ground-level object at
d = 22..120 px (elevation 0, theta = 2 atan(8/d) exactly, 40 deg at d = 22), never on game outcomes. Not derived from E1 or any run. Channel: LPLC2 (theta,
rad) and LC4 (|dtheta|, rad/frame), both hemispheres for a frontal object. The disc test drives the brain through the same mechanism.
DNp02's EMA pool of the legacy path is not part of the manifest.

## 7. Motor map (fixed)

GF/TTMn -> A through a leaky integral of the TTMn onset (GF drives TTMn through the wiring; the muscle is read at TTMn); DNp09 -> walk
(right) and B; DNa01/DNa02 right-minus-left team -> right or left; MDN -> back up (left button); Down and Up unassigned. Left wins
over right when both. Reading fires nothing.

## 8. Validation

- Rest: no stimulus -> GF silent, motor map silent, real and shuffled.
- Disc: GF firing angle for l/v 10/20/40/80 ms, real vs 5 shuffles with the same fixed numbers; gate as stated at the top (38-48 deg,
  spread <= 8 deg, shuffled do not fire).
- Tests (`tests/test_brain_core.py`): manifest counts; sparse W equals `circuit.build_weight_matrix` on a toy subnet; shuffle preserves
  degrees and signs; path-union finds exactly the on-path neurons on a toy graph; the stimulus API rejects non-sensory ids and writes
  only to sensory neurons; no public method adds current elsewhere; calibration-hash mismatch raises; motor map is read-only and
  leaves Down/Up unpressed; stamp carries rule, hash, mechanisms. Network-dependent tests use the cached network and skip with a
  reason if the weights file has not been streamed.
- Known risk, reported not re-tuned: the rest thresholds (mean + 6 std) leave a thin margin on shuffled wiring. Over 2000 rest frames
  the shuffled rest maximum came within about 8 % (steer) and 14 % (back) of the threshold (real: 15-30 % below). A motor-map false
  positive at rest on a shuffled brain is therefore possible; `brain.disc.rest_margin` and `calibrate.report` print max/threshold
  ratios and a test records them for real and shuffled. The thresholds are not changed.
- Network stamp edge counts: 592,683 built edges (the rule's edges, as Phase 0 expected) and 568,527 non-zero weights. The
  24,156 difference is the outgoing edges of the 430 neurons whose predicted transmitter is unknown (sign 0, dropped as sources:
  `BuiltNetwork.edge_report`, in every `Brain.stamp()`). None of the 430 is an output neuron or an LC4/LPLC2 looming input; 13 are head
  GRNs (sensory, no mechanism drives them yet) and 2 are DANs; the rest are interior neurons. `edges` in the saved rule counts the
  non-zero weights.
- Root `tests/` run once at the end (goldens must remain byte-identical).
- Not done in this phase: E0/E1. The 20-seed eval has since been run (section 9): the gate was not testable.

## 9. Standard eval (Phase 1 gate), wired in fix round 1

`python -m scripts.eval_brain --workers 8` (`brain/evaluation.py`): level 1-1 from reset, `BrainPolicy` only, real connectome vs a
degree-preserving shuffle (shuffle seed 1 + i), seeds 2000-2019 (fresh, held out), metric "past the first Goomba" (Mario's world x
beyond the first Goomba's spawn x while alive) with Wilson 95% intervals (`tool.core.evaluation.wilson_ci`). It does not use
the legacy `tool/core/runner.py` path. Only a 1-seed smoke check (seed 9000) has been run by the implementer; the experimenter runs the
20 seeds once. Note: Phase 1 has no goal cue (D2 is Phase 3), so Mario stands unless the brain itself drives walking; the metric is
meaningful only once a drive exists, and a 0/20 here is expected until then. The E1 scene (a controlled Goomba approach) is Phase 2;
the earlier proxy E1 result is reported as "not tested".

**Result (audit/p1r2_eval.json, seeds 2000-2019, 1500 frames max).** Real 0/20 past the first Goomba, shuffled 0/20, Wilson 95% CI
0-16.1% for each. No deaths, no GF spike, no A press; every episode ended at the 1500-frame limit with max_x = 40 and goomba_x = None
(the first Goomba was never seen, because Mario never walks). The Phase 1 gate (real >= 16/20) was NOT TESTABLE (not failed). The reason is structural:
with no goal cue (D2, Phase 3) Mario stands still, so in Phase 1 the metric cannot discriminate real from shuffled at all; the result
says nothing about the brain's looming circuit, which the disc test covers.

Sprite geometry caveat: the 16 px sprite / 8 px Y-byte offset used for enemy centres (section 6) is validated for small Mario vs a
Goomba on flat ground only. Re-validate in Phase 2 before Koopas or other tall enemies, and for big Mario.
