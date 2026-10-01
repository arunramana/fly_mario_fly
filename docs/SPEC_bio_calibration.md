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
| 2 | Giant Fiber | DNp01 fires at a roughly constant angular size **theta_GF = 40 deg** for l/v 20-80 ms, threshold fixed once from the real circuit and applied unchanged to shuffles | **Ache et al. 2019 Curr Biol 29:1073: GF response peaks at a consistent ~40 deg (their model 42 deg); citation verified by the user (revision 2026-09-30; the first calibration used 55 deg from memory).** Sanity checks only, not targets: Fotowat et al. 2009 report 49-54 deg for takeoff *behaviour*, mostly not GF-mediated; Card & Dickinson 2008 Curr Biol 18:1300 is used for timing only |
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

## Results (revision 2026-09-30: target theta_GF = 40 deg, Ache et al. 2019)
The first calibration (55 deg, from memory) is superseded; its eval was real 390 (363-416) / 569 (487-651) vs shuffled 310 for the two wall
conditions. Nothing else changed in this revision (same stability gains, same procedure, same eval, run once).

### Calibrated values and derivations (`scripts/calibrate_bio.py`, real circuit, disc only)
| value | result | derivation |
|---|---|---|
| recurrent gains | unchanged: jump 1.035, speed 1.027, steering 1.082, mdn 1.157; dnp02 1.2, takeoff 0.8 | `g = min(g, 0.85 / rho(W_real))`; shuffles get the same g |
| `gf_threshold` | **0.25077** (was 0.34994) | mean DNp01 spike-cell membrane at theta = 40 deg over l/v 20/40/80: 0.2595 / 0.2495 / 0.2433 (6 % spread) |
| `dnp02_input_gain` | **14.805** | DNp02's raw membrane at 40 deg, l/v 10, is 0.0169 (noise floor); the gain puts it on the GF scale |
| `dnp02_threshold` | **0.25077** | = `gf_threshold` |
| `ttmn_unit_factor` | **1.403** (was 1.275) | peak TTMn clip 200/spike 60 over 50/50, same disc and circuit: 1.20 / 1.24 / 1.77 (l/v 20/40/80) |
| `dlmn_unit_factor` | **1.275** (was 1.224) | same for DLMn: 1.25 / 1.28 / 1.30 |
The unit factors are re-measured by the script with the new threshold (it enters the spiking disc); they moved by 10 % / 4 %.
Literature use: **Ache et al. 2019 (GF peak ~40 deg, model 42 deg) is the target**; Fotowat et al. 2009 (49-54 deg) is behaviour, mostly
non-GF: sanity check only; Card & Dickinson 2008 is used for timing only.

### Disc curves, real vs shuffled (same fixed numbers; GF = first DNp01 spike; time = before collision)
Rest (2000 frames, sigma 0.015): real and all 5 shuffles silent (TTMn <= 0.035, DNp01 0, DNp02 0, DLMn <= 0.017, 0 spikes).

| l/v | real GF | real peak TTMn | shuffles 1-5 GF (deg) | shuffles peak TTMn | real DNp02 |
|---|---|---|---|---|---|
| 10 ms | 47 deg (23 ms) | 13.8 | 116, 116, 116, 116, 116 | 0.7-2.4 | 47 deg |
| 20 ms | **47 deg** (46 ms) | 19.9 | 69, 69, 116, 69, 69 | 0.7-2.5 | 47 deg |
| 40 ms | **41 deg** (108 ms) | 24.4 | 56, 69, 88, 69, 69 | 0.9-3.4 | 56 deg |
| 80 ms | **44 deg** (200 ms) | 22.4 | 56, 62, 88, 62, 69 | 0.9-3.5 | 62 deg |

Real: 41-47 deg across l/v 10-80 (target 40, spread 6 deg, constant to within one frame of sampling, 17 ms). Shuffles with the same numbers: later
(56-116 deg), 3-10x weaker TTMn, DNp02 silent except shuffle 4 (116-135 deg, mistimed). One sample per frame limits l/v 10 (the next sample is already
at ~60 deg).

### Standard eval (honest_1 #36 settings + bio_strict + calibration; 20 held-out seeds 1000-1019, real vs degree-preserving shuffle; run once)
| condition | arm | wins | max_x mean (95% CI) | median | runs past the first Goomba (x >= 400) |
|---|---|---|---|---|---|
| walls as #36 | real | 0/20 | **408 (381-428)** | 434 | 16/20 |
| | shuffled | 0/20 | **310 (309-310)** | 310 | 0/20 |
| + wall looming route | real | 0/20 | **616 (540-682)** | 712 | 16/20 (13 reach x >= 600) |
| | shuffled | 0/20 | **310 (309-310)** | 310 | 0/20 |

Real differs from shuffled in both conditions (disjoint CIs). Versus the 55 deg calibration: 16/20 (was 13/20) real runs pass the first Goomba and
13/20 reach the second obstacle with the wall route (x 694-724; three more stop at x ~595); still 0 wins (the fly does not clear the pipes, pits are
unperceived) and 4/20 real runs fail at the first Goomba (x 299-302).

### Step 6: odour vs `home_bias` (documented, nothing changed)
Odour = `odour_gain` 16 x (hunger x3 when small Mario) / distance; `home_bias` = 1.0 on the R team. Food odour beats `home_bias` inside **48 px
(3 tiles)** when hungry (3.0 at 16 px, 6.0 at 8 px), 16 px when sated; aversive odour (no hunger term) beats it inside 16 px. A `?` block
behind Mario on screen can therefore hold him at the screen's left edge (seen in the diagnosis: seeds 1000/1003). Steering fix = a later decision.
