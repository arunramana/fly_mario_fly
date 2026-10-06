# SPEC: walking-speed dose-response (declared 2026-10-05, before any run)

Question: does the speed at which Mario reaches the first Goomba change whether he survives it? This is a dose-response curve, not
tuning. No value is adopted afterwards; the registered `GOAL_CUE_SALIENCE` stays 15 and calibration and motor thresholds are untouched.

## Design
- Experiment: the 1-1 innate baseline B11 (`brain/baseline.py`; obstacle expansion ON, looming + pursuit + home landmark), unchanged.
- Independent variable: `GOAL_CUE_SALIENCE` = 5, 8, 11, 15 (15 = registered default). Per neuron, onto the right LC10a only.
- Window: `GOAL_CUE_SALIENCE` sits in the window validated as about 3-25 per neuron (docs/INVESTIGATION_phase3.md; the calibration recorded
  5-25 as the goal window, midpoint 15). 5 is near the low edge; 8 and 11 are inside; nothing outside the window is tested.
- Seeds: fresh 6200-6219 for EVERY value (same 20 seeds per value, run once). Arms: real and degree-preserving shuffle (shuffle seed 1+i).
  Class-preserving shuffle not run. The shuffled arm gets the same cue.
- Override path: `brain/dose_response.py` builds `SenseSettings(goal_cue_salience=V)` and passes it through `settings_for("B11", ...)`,
  so only the landmark strength differs; the stamp (`senses`) records V. `calibration.GOAL_CUE_SALIENCE` is never modified.
  `brain/baseline.py` gained only an optional read-only `probe` argument (None = every earlier run unchanged, byte-identical).

## Metrics (defined before running; all measured from RAM)
1. Walking speed = mean Mario world-x speed in px/frame = (x[W] - x[0]) / W, x = page*256 + x position, x[0] read after reset,
   W = min(100, frame of first Goomba contact, last frame of the episode). Window: frames 1..W. First Goomba contact = first frame an active
   Goomba is within 16 px (`SPRITE_PX`) horizontally of Mario.
2. Survival at the first Goomba: survived = Mario alive when that Goomba is entirely behind him (dx <= -16) or removed (stomped or gone);
   died_enemy = the episode ended as `died_enemy` before that; unresolved = ended another way (stuck, pit, timeout) before resolving;
   no_contact = never reached a Goomba. Wilson CI over episodes that reached contact.
3. max_x: mean with percentile-bootstrap 95% CI, median.
4. End reasons (baseline classification), Goombas jumped / encountered (corrected tracker), pipe-1 cleared (max_x > 479), A-tap fraction.
5. Whether the contact frame and Mario's x at contact change with speed (mean, median, CI per value).
Output: one json (`--out`) with the full curve (value x arm table) and per-episode rows; the curve table is printed.

## Run
`.venv/Scripts/python.exe -m brain.dose_response --workers 8 --out projects/<name>/runs/NNN_dose_response.json` (defaults: values 5 8 11 15,
n 20, seed0 6200, arms real shuffled). Interpretation (not part of the metrics): a speed change with unchanged survival, or the reverse,
is reported as measured; no criterion, no adopted value.

## Validation / tests
`tests/test_baseline.py`: the override changes only `goal_cue_salience` (settings equal the default except that field), the absent override
returns the default settings and an identical stamp, the registry value stays 15, the probe is optional and writes no RAM, and the speed
window and first-Goomba classification on a fake probe. Smoke on seed 9100 only (2 values, 400 frames) before the declared run.
