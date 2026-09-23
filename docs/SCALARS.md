# Scalars

Every hand-set scalar in the live system, generated directly from
`config/params.py` -- not recalled from memory, not re-derived by reading
comments across a dozen files. Regenerate after any change to that file:

```
.venv/Scripts/python.exe -m config.scalars_doc
```


`tests/test_scalars_doc.py` fails if this file and `config/params.py`
disagree.

**The count phase 4 was asked to produce, without softening:** this
project's own running comments had been tracking a "budget" of 3, then 5,
then 8, then 9 hand-set neural/mechanical scalars across 26 sprints.

## NetworkParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `alpha` | `0.3` | unknown | measured (spec-level, sprint 1: leak time constant ~= 1/alpha substeps) | `fly/network/dynamics.py (ALPHA)` |
| `clip` | `50.0` | unknown | invented (spec-level, sprint 1: arbitrary firing-rate ceiling) | `fly/network/dynamics.py (CLIP)` |
| `substeps` | `10` | unknown | measured (spec-level, sprint 1: 60fps frame = 16.7ms, ~1.67ms/substep) | `fly/network/dynamics.py (SUBSTEPS)` |

## NoiseParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `sigma` | `0.0` | 0.04-0.06 | measured (025's calibration sweep: smallest sigma giving a whole-frame commitment-time spread across 50 seeds while DNp01 still commits in every episode; 0.07+ is a qualitatively different, pathway-failing regime) | `run_steering.py main()'s sigma= default` |

## JumpParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `2.0` | 1.12-3.35 | measured (diag4.py Diagnostic-4 sweep against the real 1255-neuron subgraph; band checked robust across 5 random trace seeds) | `run_mario.py (G)` |
| `dnp01_spike_threshold` | `0.5` | unknown | measured (diag4.py sweep) | `run_mario.py (DNP01_SPIKE_THRESHOLD)` |
| `ttmn_press_threshold` | `3.0` | unknown | measured (diag4.py sweep) | `run_mario.py (TTMN_PRESS_THRESHOLD)` |
| `spike_amp` | `50.0` | unknown | measured (matched to CLIP -- a spike is a full-scale event) | `run_mario.py (SPIKE_AMP)` |
| `jump_hold_frames` | `25` | unknown | invented (mechanical output-interface constant, not part of the neural model, per this project's own convention since sprint 006) | `run_mario.py (JUMP_HOLD_FRAMES)` |
| `jump_cooldown_frames` | `40` | unknown | invented (mechanical output-interface constant) | `run_mario.py (JUMP_COOLDOWN_FRAMES)` |

## Dnp02Params

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (tune_dnp02.py/tune_dnp02_widen.py, kept <=0.85x the real spectral-radius boundary -- a per-matrix constraint, not a fixed numeric range) | `run_steering.py (G_DNP02)` |
| `spike_threshold` | `0.1` | unknown | measured | `run_steering.py (DNP02_SPIKE_THRESHOLD)` |
| `alpha` | `0.1` | unknown | invented (a slow EMA rate on DNp02's own input current, giving it "longer integration" without slowing HybridState's shared alpha -- sprint's own bug-fix choice, not connectome-derived) | `run_steering.py (DNP02_ALPHA)` |

## TakeoffParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `0.8` | unknown | measured (tune_terrain.py) | `run_steering.py (G_TAKEOFF)` |
| `gap_gain` | `0.6` | unknown | invented (external current per non-ground tile ahead onto DNp01 -- no real synapse carries terrain information, same modelling category as HOME_BIAS/WALK_DRIVE/MDN_DRIVE) | `run_steering.py (GAP_GAIN)` |
| `dlmn_recruit_threshold` | `1.0` | unknown | measured (tune_terrain.py: sits between the width-1 and width-2 DLMn end-of-frame means) | `run_steering.py (DLMN_RECRUIT_THRESHOLD)` |
| `long_jump_hold_frames` | `35` | unknown | invented (mechanical output-interface constant) | `run_steering.py (LONG_JUMP_HOLD_FRAMES)` |
| `gap_lookahead_tiles` | `8` | unknown | invented (perceptual range, mechanical, not a circuit gain) | `run_steering.py (GAP_LOOKAHEAD_TILES)` |

## SpeedParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (tune_terrain.py) | `run_steering.py (G_SPEED)` |
| `walk_drive` | `1.0` | unknown | invented (constant "walk" current, no real synapse carries it) | `run_steering.py (WALK_DRIVE)` |
| `walk_suppression` | `1.0` | unknown | invented (cancels WALK_DRIVE while jumping/stalled) | `run_steering.py (WALK_SUPPRESSION)` |
| `dnp09_speed_threshold` | `0.5` | unknown | measured | `run_steering.py (DNP09_SPEED_THRESHOLD)` |

## SteeringParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (tune_steering.py) | `run_steering.py (G_STEER)` |
| `home_bias` | `1.0` | unknown | invented (constant "go home" current, R-hemisphere only; no real synapse carries it -- explicitly a placed bias, not a scaling error to fix by lowering it, per SPEC_odour.md section 0) | `run_steering.py (HOME_BIAS)` |
| `climb_stall_frames` | `20` | unknown | invented (mechanical: mario_x unchanged this long while steering=R -> blocked; diagnosed via A/B, see docs/RUNS.md sprint on habituation -- 15->40 was checked and changed nothing) | `run_steering.py (CLIMB_STALL_FRAMES)` |
| `climb_hop_small_frames` | `10` | unknown | invented (mechanical, small Mario's first-try hop) | `run_steering.py (CLIMB_HOP_SMALL_FRAMES)` |
| `climb_hop_big_frames` | `14` | unknown | invented (mechanical, big Mario's taller hitbox) | `run_steering.py (CLIMB_HOP_BIG_FRAMES)` |
| `climb_jump_frames` | `25` | unknown | invented (mechanical, same magnitude as the escape jump hold) | `run_steering.py (CLIMB_JUMP_FRAMES)` |
| `climb_cooldown_frames` | `15` | unknown | invented (mechanical) | `run_steering.py (CLIMB_COOLDOWN_FRAMES)` |
| `climb_clear_distance` | `24` | unknown | invented (mechanical, px of forward progress that resets the attempt counter) | `run_steering.py (CLIMB_CLEAR_DISTANCE)` |

## MdnParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (tune_mdn.py: real spectral radius 0.7345, comfortably under its ~1.36 linear boundary) | `run_steering.py (G_MDN)` |
| `mdn_drive` | `2.0` | unknown | invented (external current -- no real DNp01/GFC1-4 synapse onto MDN in this connectome, checked) | `run_steering.py (MDN_DRIVE)` |
| `mdn_threshold` | `1.0` | unknown | measured (tune_mdn.py) | `run_steering.py (MDN_THRESHOLD)` |
| `mdn_backup_frames` | `30` | unknown | invented (mechanical, fixed-duration corrective backup) | `run_steering.py (MDN_BACKUP_FRAMES)` |

## MushroomBodyParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `kc_sparsity` | `0.05` | unknown | measured (matches the real fly's ~5% concurrently-active KC fraction, enforced structurally via top-k rather than simulating the real APL feedback-inhibition neuron) | `run_steering.py (KC_SPARSITY)` |
| `trace_decay` | `60.0` | unknown | measured (~1s at 60Hz, the real eligibility-trace timescale asked for) | `run_steering.py (TRACE_DECAY)` |
| `learning_rate` | `0.001` | unknown | invented (chosen by direct isolated verification against a hand-computed dW on a real KC->MBON weight -- the first guess, 0.01, was rejected on that same test as too aggressive) | `run_steering.py (LEARNING_RATE)` |

## HabituationParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `hab_progress_px` | `16` | unknown | invented (one tile -- same "did that actually help" bar CLIMB_CLEAR_DISTANCE uses, deliberately smaller) | `fly/state/reflex_habituation.py (HAB_PROGRESS_PX)` |
| `hab_give_up` | `3` | unknown | invented (consecutive no-progress firings before a reflex suppresses itself) | `fly/state/reflex_habituation.py (HAB_GIVE_UP)` |

## OdourParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `odour_gain` | `16.0` | unknown | invented (chosen by simulating the real steering circuit end to end, tune_odour.py -- the smallest gain that makes a close (16px) encounter cross HOME_BIAS's settled output in the actual recurrent network; fixes a 40x unit mismatch, not a connectome-derived value) | `run_steering.py (ODOUR_GAIN)` |
| `hunger_mult_hungry` | `3.0` | unknown | measured (tune_odour.py sweep: smallest value that still flips the WTA at d=40px) | `bridge/perception.py (HUNGER_MULT_HUNGRY)` |
| `hunger_mult_sated` | `1.0` | unknown | invented (unboosted baseline, not zeroed) | `bridge/perception.py (HUNGER_MULT_SATED)` |
| `alpha_adapt` | `0.011111111111111112` | unknown | measured (~1.5s time constant at 60fps, the real ORN adaptation timescale asked for) | `fly/sensing/olfactory_adaptation.py (ALPHA_ADAPT)` |

## TerrainParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `refusal_gap_tiles` | `5` | unknown | invented (mechanical body-scaled threshold, derived from prior calibration boundaries: 007's clean 0-4-tile GAP_GAIN sweep and 008/011's 8-tile failure -- "refuse anything not already shown to work", not a circuit gain) | `run_steering.py (REFUSAL_GAP_TILES)` |

## EntityParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `entity_width_px` | `16` | unknown | invented (every enemy-slot entity assumed this wide for the looming-angle calculation, real Goomba/Koopa/mushroom hitboxes differ in real SMB and this project has never modelled that) | `mario/entities/registry.py (ENTITY_WIDTH_PX)` |

## RetinotopyParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `azimuth_d_ref` | `128.0` | unknown | invented (retinotopy.py's own docstring: "the one invented numeric scaffold, stated plainly" -- half the NES screen width, used only as an arbitrary but stated saturation point; no principled reference distance exists in hex coordinates) | `fly/sensing/retinotopy.py (AZIMUTH_D_REF)` |
| `hex1_spread_fallback` | `3.0` | unknown | invented (fallback bandwidth for a cell with no measured hex-carrying input -- verified empty case in practice; NOT named as a module constant in the live code, only a literal inside receptive_field_centers(), found while building this file, not previously flagged anywhere) | `fly/sensing/retinotopy.py (receptive_field_centers, literal)` |
| `hex1_spread_floor` | `0.5` | unknown | invented (floor on a single-partner cell's measured spread, which would otherwise be exactly zero and make its tuning curve a delta function; same as above, a bare literal, not a named constant, found while building this file) | `fly/sensing/retinotopy.py (receptive_field_centers, literal)` |

## DemoParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `mushroom_offset` | `-40` | unknown | invented (spawn position for the synthetic mushroom-injection demo, behind Mario so it competes with HOME_BIAS's rightward pull) | `run_steering.py (MUSHROOM_OFFSET)` |


## What this doc is not

A range of `unknown` means genuinely unknown -- not measured, not
documented anywhere in this project's own sprint history, and not invented
here to fill the cell. Per this phase's own instruction: an invented bound
is scaffolding that looks like data. Most fields in this table are
`unknown` for exactly that reason; the two with a real documented range
(`JumpParams.g`, `NoiseParams.sigma`) have one because a specific sprint
(diag4.py's Diagnostic-4 sweep; 025's calibration sweep) actually
characterised it.

**Total: 49 hand-set scalars** -- larger than either "8" or "9", the
two numbers this project's own comments had been citing. Three of the
49 (`RetinotopyParams`'s fields) are dormant: no golden-tested run
exercises `retinotopic=True`. One (`DemoParams.mushroom_offset`) only
matters when a caller explicitly opts into the synthetic-injection demo.
The other 45 are live in every default run.

## Invented / measured / connectome-derived

Split by the first word of each field's own `provenance` text above, not a
second hand-maintained tally: **29 invented**, **20 measured**, **0 connectome-derived** (of 49).

**Zero are connectome-derived**, and that's the real finding, not an
artifact of the split: the connectome determines the WEIGHT MATRIX each
circuit steps (`W`, one per circuit, streamed from the real synapse data --
CLAUDE.md invariant 2), but every one of these 49 numbers sits outside
that matrix -- a gain multiplying it, a threshold compared against its
output, or a mechanical hold duration with no neural meaning at all. The
connectome constrains what these circuits CAN compute; it has never
supplied a single one of the scalars controlling how hard they push on
that computation. "Measured" means simulated against the real W and
picked by a sweep (`tune_*.py`/`diag4.py`) or matched to a real biological
timescale/fraction -- a real number, but still chosen, not read off the
data the way `W` itself is. **Invented outnumbers measured (29 vs 20)**:
most of what this project calls "the model" is mechanical scaffolding
(hold durations, cooldowns, body-scaled thresholds) and placed external
currents (`HOME_BIAS`, `GAP_GAIN`, `WALK_DRIVE`, `MDN_DRIVE` and others --
explicitly flagged throughout this project's own comments as currents no
real synapse carries), not calibrated circuit dynamics.
