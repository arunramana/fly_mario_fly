# SPEC: bio_strict calibration (from docs/DIAG_bio_strict_escape.md, plan steps 1-7)

Scope: only under `config.bio_strict` (default off; every golden unchanged). **Validation is on the synthetic looming disc and
on resting-state tests only; nothing is tuned on game runs.** The eval at the end is reported, not optimised. Every number below
is either *measured* (derived by `scripts/calibrate_bio.py` from the real circuit + disc) or an explicitly flagged *target*.
Literature targets are from memory and **must be verified by the user** (confidence given).

## Shared test bench (`bridge/loom_disc.py`)
- **Disc:** constant-approach disc, l/v = 10, 20, 40, 80 ms (l = half-size, v = speed): `theta(t) = 2 atan((l/v)/tau)`,
  `tau` = time to collision, start at 2 deg, one sample per 16.7 ms frame. Inputs exactly as the strict fly gets them: |dtheta|
  (rad/frame) -> LC4 (both hemispheres, frontal), theta (rad) -> LPLC2; DNp02 gets the EMA of |dtheta| on its LC4 pool;
  DNp01 -> takeoff circuit gives DLMn. No game, no salience multiplier.
- **Rest:** 2000 frames, zero stimulus, per-neuron noise sigma = 0.015 (the project's value), all networks.

## Targets
| # | what | target | source / confidence |
|---|---|---|---|
| 1 | stability | linearised loop gain `rho(W)*g <= 0.85` for every recurrent circuit (jump, takeoff, speed, steering, mdn, dnp02, posture); rest test: TTMn, DNp01, DNp02, DLMn < 0.5 over 2000 frames at sigma 0.015, real **and** shuffled | dynamical-systems criterion (rho*g < 1 = no runaway) with a 15 % margin for noise; high |
| 2 | Giant Fiber | DNp01 fires at a roughly constant angular size **theta_GF = 55 deg** for l/v 20-80 ms, threshold fixed once from the real circuit and applied unchanged to shuffles | von Reyn et al. 2014 Nat Neurosci 17:1 (GF angular-size threshold ~50-60 deg, largely independent of l/v), Card & Dickinson 2008 Curr Biol 18:1300 (takeoff at comparable thresholds): **medium-low; please verify** |
| 3 | motor units | motor thresholds expressed in the new units by the **measured** TTMn / DLMn unit factors (peak response to the same disc at clip 200 / spike 60 vs clip 50 / spike 50); time constants (`adapt_frames`, `decay`) are not rescaled | derived from the disc (no outcome tuning); high (it is a measurement) |
| 4 | DNp02 | threshold set so DNp02 (LC4-rate driven) fires at theta_GF for the fastest disc (l/v 10 ms) and therefore not for slow ones -- same derivation as the GF, one number | DNp02 as the rate-sensitive second escape DN (Ache et al. 2019 Curr Biol 29:1073; von Reyn 2017 Neuron 94): **low** |
| 5 | walls | wall-as-expanding-object looming route (`wall_ahead.looming_gain`) re-evaluated with the calibrated circuit; stays opt-in | - |
| 6 | odour vs `home_bias` | **document only** (no change): magnitudes vs distance | - |

## Procedure (`scripts/calibrate_bio.py`, real circuit only)
1. `g_stable = margin / rho(W)` per circuit (`BioStrictParams.stability_margin = 0.85`), applied to whichever `W` is used (real or
   shuffled -- a stability normalisation, like the spike threshold it is not tuned per circuit).
2. Run each disc with spiking disabled, record the DNp01 spike-cell membrane `mem(theta)`; pick `gf_threshold` = mean over
   l/v 20-80 of `mem` at theta_GF (the real circuit's own curve). Report the resulting theta_fire for l/v 10-80 and the same
   fixed threshold on 5 degree-preserving shuffles.
3. Repeat for DNp02 at l/v 10 -> `dnp02_threshold`.
4. Unit factors: same disc, same circuit, clip/spike 50/50 vs 200/60 (spike on): ratio of peak TTMn, of peak DLMn.
5. Values go into `BioStrictParams` (provenance "measured ... scripts/calibrate_bio.py") and `config/bio_strict.py::effective`.

## Reporting (Results section below is filled in after the runs)
Disc curves real vs shuffled, rest test, and the standard 20-seed eval (seeds 1000+, real vs degree-preserving shuffle) with
honest_1 #36 settings + bio_strict + calibration, with and without the wall looming route. **Success = real differs from
shuffled, not wins.**

## Results (2026-09-30)

### Calibrated values and derivations (`scripts/calibrate_bio.py`, real circuit, disc only)
| value | result | derivation |
|---|---|---|
| recurrent gains | jump 1.035 (was 2.0 / 2.6), speed 1.027, steering 1.082, mdn 1.157; dnp02 1.2 and takeoff 0.8 unchanged | `g = min(g, 0.85 / rho(W_real))`; rho: jump 0.821, speed 0.827, steering 0.786, mdn 0.734, dnp02 0.573, takeoff 1.000. Shuffles get the same g |
| `gf_threshold` | **0.34994** | mean of the DNp01 spike-cell membrane at theta = 55 deg over l/v 20/40/80 (0.364 / 0.348 / 0.338: 7 % spread) |
| `dnp02_input_gain` | **14.796** | DNp02's raw membrane at 55 deg for l/v 10 is 0.0237, at the noise floor (it fired at rest); the gain puts it on the GF's scale |
| `dnp02_threshold` | **0.34994** | = `gf_threshold` (one membrane scale) |
| `ttmn_unit_factor` | **1.275** | peak TTMn, same disc and circuit, clip 200 / spike 60 over clip 50 / spike 50: 1.35 / 1.24 / 1.24 (l/v 20/40/80) |
| `dlmn_unit_factor` | **1.224** | same for DLMn: 1.16 / 1.21 / 1.29 |

The expected "~3.5x" factor does **not** appear: it was measured on the supercritical, latched circuit (g 2.6); with the stable
gain the unit change is only ~1.28x. Applied as `jump.ttmn_press_threshold x 1.275` and `motor_direct.dlmn_gain / 1.224`;
`a_threshold` and `ttmn_gain` act on the TTMn *ratio* (TTMn / threshold), so they keep their meaning unchanged; `adapt_frames`
and `decay` are time constants and are not rescaled.

### Disc curves, real vs shuffled (same fixed numbers; GF = first DNp01 spike; "x ms" = time before collision)
Rest (2000 frames, sigma 0.015): real and all 5 shuffles stay silent (TTMn <= 0.035, DNp01 0, DNp02 0, DLMn <= 0.017, 0 spikes).

| l/v | real GF | real peak TTMn | shuffles 1-5 GF (deg) | shuffles peak TTMn |
|---|---|---|---|---|
| 10 ms | 116 deg (6 ms; one frame is already 17 ms) | 10.7 | 116 x5 | 0.7-2.4 |
| 20 ms | **69 deg** (29 ms) | 10.8 | 116 x5 | 0.7-2.5 |
| 40 ms | **56 deg** (75 ms) | 18.6 | 88, 88, 116, 88, 116 | 0.9-3.4 |
| 80 ms | **62 deg** (133 ms) | 21.0 | 77, 88, 116, 88, 100 | 0.9-3.5 |

Real: 56-69 deg for l/v 20-80 (target 55 deg, spread 13 deg), the right form (angle roughly constant, time-to-collision scaling with l/v: 29, 75, 133 ms).
Shuffles: later (77-116 deg), mistimed, 3-10x weaker muscle-neuron response, DNp02 silent (one stray spike at 157 deg). DNp02 real: 69-77 deg for l/v 20-80.
Limits: l/v 10 ms is not resolvable at one sample per frame (the disc goes from ~60 to 116 deg between frames); the 55 deg target is the literature
value flagged medium-low confidence (please verify); the threshold was fixed at 55 deg, so "real ~ 55" is by construction at that point and the
informative results are the constancy across l/v and the shuffle contrast.

### Step 6: odour vs `home_bias` (documented, nothing changed)
Odour = `odour_gain` 16 x (hunger x3 when small Mario) / distance; `home_bias` = 1.0 on the R team. Food odour beats `home_bias` inside **48 px
(3 tiles)** when hungry (3.0 at 16 px, 6.0 at 8 px), 16 px when sated; aversive odour (no hunger term) beats it inside 16 px. A `?` block
behind Mario on screen can therefore hold him at the screen's left edge (seen in the diagnosis: seeds 1000/1003). Steering fix = a later decision.

### Step 5 + step 7: standard eval (honest_1 #36 settings + bio_strict + calibration; 20 held-out seeds 1000-1019, real vs degree-preserving shuffle)
| condition | arm | wins | win rate (CI) | max_x mean (CI) | median |
|---|---|---|---|---|---|
| calibrated, walls as #36 (`looming_gain` 0) | real | 0/20 | 0 % (0-16) | **390 (363-416)** | 434 |
| | shuffled | 0/20 | 0 % (0-16) | **310 (309-310)** | 310 |
| calibrated + wall looming route (`looming_gain` 1.0) | real | 0/20 | 0 % (0-16) | **569 (487-651)** | 700 |
| | shuffled | 0/20 | 0 % (0-16) | **310 (309-310)** | 310 |
| (before calibration, for reference, from SPEC_bio_strict) | real / shuffled | 0 / 0 | - | 331 (303-359) / 328 (310-347) | 298 / 310 |

**Real differs from shuffled (disjoint CIs in both conditions): the success criterion.** 13/20 real runs now pass the first Goomba (max_x >= 434, the
first pipe) vs 0/20 shuffled (all 20 die at 308-311, the first Goomba); with the wall route 13/20 reach x 683-725 (the second obstacle) vs 0/20.
Still no wins: the fly does not clear the pipes, the pits are unperceived, and 7/20 real runs still fail at the first Goomba (x 300-310). Not done: any
tuning on these runs (none was); steering/odour, a pit route, trained MB.
