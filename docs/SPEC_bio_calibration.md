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
