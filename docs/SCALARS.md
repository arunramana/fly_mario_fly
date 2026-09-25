# Scalars

Every hand-set scalar in the system, generated from `config/params.py`.
Regenerate after any change to that file:

```
.venv/Scripts/python.exe -m config.scalars_doc
```

`tests/test_scalars_doc.py` fails if this file and `config/params.py`
disagree.

## NetworkParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `alpha` | `0.3` | unknown | measured (spec-level, sprint 1: leak time constant ~= 1/alpha substeps) | `fly/network/dynamics.py (ALPHA)` |
| `clip` | `50.0` | unknown | invented (spec-level, sprint 1: arbitrary firing-rate ceiling) | `fly/network/dynamics.py (CLIP)` |
| `substeps` | `10` | unknown | measured (spec-level, sprint 1: 60fps frame = 16.7ms, ~1.67ms/substep) | `fly/network/dynamics.py (SUBSTEPS)` |
| `denormal_flush_threshold` | `1e-30` | unknown | invented (docs/CODE_AUDIT.md section H: numerical hygiene -- anything below this is flushed to exactly 0.0 so subnormal floats don't slow the matvec; not a claim about a real biological floor. The jump circuit deliberately does NOT call flush_denormals -- CLAUDE.md's own GPU section: fixing that re-baselines every golden and needs its own dedicated sprint) | `fly/network/network.py (Network.flush_denormals's own default) and bridge/full_policy.py's h_mbon inline flush` |

## NoiseParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `sigma` | `0.0` | 0.04-0.06 | measured (025's calibration sweep: smallest sigma giving a whole-frame commitment-time spread across 50 seeds while DNp01 still commits in every episode; 0.07+ is a qualitatively different, pathway-failing regime) | `run_steering.py main()'s sigma= default` |

## JumpParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `2.0` | 1.12-3.35 | measured (scripts/diag4.py Diagnostic-4 sweep against the real 1255-neuron subgraph; band checked robust across 5 random trace seeds) | `run_mario.py (G)` |
| `dnp01_spike_threshold` | `0.5` | unknown | measured (scripts/diag4.py sweep) | `run_mario.py (DNP01_SPIKE_THRESHOLD)` |
| `ttmn_press_threshold` | `3.0` | unknown | measured (scripts/diag4.py sweep) | `run_mario.py (TTMN_PRESS_THRESHOLD)` |
| `spike_amp` | `50.0` | unknown | measured (matched to CLIP -- a spike is a full-scale event) | `run_mario.py (SPIKE_AMP)` |
| `jump_hold_frames` | `25` | unknown | invented (mechanical output-interface constant, not part of the neural model) | `run_mario.py (JUMP_HOLD_FRAMES)` |
| `jump_cooldown_frames` | `40` | unknown | invented (mechanical output-interface constant) | `run_mario.py (JUMP_COOLDOWN_FRAMES)` |

## Dnp02Params

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (scripts/tune_dnp02.py/scripts/tune_dnp02_widen.py, kept <=0.85x the real spectral-radius boundary -- a per-matrix constraint, not a fixed numeric range) | `run_steering.py (G_DNP02)` |
| `spike_threshold` | `0.1` | unknown | measured | `run_steering.py (DNP02_SPIKE_THRESHOLD)` |
| `alpha` | `0.1` | unknown | invented (a slow EMA rate on DNp02's own input current, giving it "longer integration" without slowing HybridState's shared alpha) | `run_steering.py (DNP02_ALPHA)` |

## TakeoffParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `0.8` | unknown | measured (scripts/tune_terrain.py) | `run_steering.py (G_TAKEOFF)` |
| `gap_gain` | `0.6` | unknown | invented (external current per non-ground tile ahead onto DNp01 -- no real synapse carries terrain information, same modelling category as HOME_BIAS/WALK_DRIVE/MDN_DRIVE) | `run_steering.py (GAP_GAIN)` |
| `dlmn_recruit_threshold` | `1.0` | unknown | measured (scripts/tune_terrain.py: sits between the width-1 and width-2 DLMn end-of-frame means) | `run_steering.py (DLMN_RECRUIT_THRESHOLD)` |
| `long_jump_hold_frames` | `35` | unknown | invented (mechanical output-interface constant) | `run_steering.py (LONG_JUMP_HOLD_FRAMES)` |
| `gap_lookahead_tiles` | `8` | unknown | invented (perceptual range, mechanical, not a circuit gain) | `run_steering.py (GAP_LOOKAHEAD_TILES)` |
| `long_jump_trigger_distance_tiles` | `2` | unknown | invented (mechanical launch-distance threshold: docs/SPEC_pits.md's own validation found the ORIGINAL threshold-only trigger firing only once the shared jump_cooldown/jump_hold timer happened to reopen, by which point Mario's own column had already advanced 2 of a 3-tile pit's own footprint -- 2 tiles of solid ground still ahead gives the 35-frame hold's arc somewhere to land) | `bridge/full_policy.py (FullPolicy.act's gap_override)` |
| `run_up_tiles` | `4` | unknown | invented (mechanical run-up distance: wider than long_jump_trigger_distance_tiles so B is already held by the time the jump itself launches -- a NES running jump clears more horizontal distance than a standing one) | `bridge/full_policy.py (FullPolicy.act's press_b override)` |

## SpeedParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (scripts/tune_terrain.py) | `run_steering.py (G_SPEED)` |
| `walk_drive` | `1.0` | unknown | invented (constant "walk" current, no real synapse carries it) | `run_steering.py (WALK_DRIVE)` |
| `walk_suppression` | `1.0` | unknown | invented (cancels WALK_DRIVE while jumping/stalled) | `run_steering.py (WALK_SUPPRESSION)` |
| `dnp09_speed_threshold` | `0.5` | unknown | measured | `run_steering.py (DNP09_SPEED_THRESHOLD)` |

## SteeringParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (scripts/tune_steering.py) | `run_steering.py (G_STEER)` |
| `home_bias` | `1.0` | unknown | invented (constant "go home" current, R-hemisphere only; no real synapse carries it -- explicitly a placed bias, not a scaling error to fix by lowering it, per SPEC_odour.md section 0) | `run_steering.py (HOME_BIAS)` |
| `climb_stall_frames` | `20` | unknown | invented (mechanical: mario_x unchanged this long while steering=R -> blocked) | `run_steering.py (CLIMB_STALL_FRAMES)` |
| `climb_hop_small_frames` | `10` | unknown | invented (mechanical, small Mario's first-try hop) | `run_steering.py (CLIMB_HOP_SMALL_FRAMES)` |
| `climb_hop_big_frames` | `14` | unknown | invented (mechanical, big Mario's taller hitbox) | `run_steering.py (CLIMB_HOP_BIG_FRAMES)` |
| `climb_jump_frames` | `25` | unknown | invented (mechanical, same magnitude as the escape jump hold) | `run_steering.py (CLIMB_JUMP_FRAMES)` |
| `climb_cooldown_frames` | `15` | unknown | invented (mechanical) | `run_steering.py (CLIMB_COOLDOWN_FRAMES)` |
| `climb_clear_distance` | `24` | unknown | invented (mechanical, px of forward progress that resets the attempt counter) | `run_steering.py (CLIMB_CLEAR_DISTANCE)` |

## MdnParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `g` | `1.2` | unknown | measured (scripts/tune_mdn.py: real spectral radius 0.7345, comfortably under its ~1.36 linear boundary) | `run_steering.py (G_MDN)` |
| `mdn_drive` | `2.0` | unknown | invented (external current -- no real DNp01/GFC1-4 synapse onto MDN in this connectome, checked) | `run_steering.py (MDN_DRIVE)` |
| `mdn_threshold` | `1.0` | unknown | measured (scripts/tune_mdn.py) | `run_steering.py (MDN_THRESHOLD)` |
| `mdn_backup_frames` | `30` | unknown | invented (mechanical, fixed-duration corrective backup) | `run_steering.py (MDN_BACKUP_FRAMES)` |

## MushroomBodyParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `kc_sparsity` | `0.05` | unknown | measured (matches the real fly's ~5% concurrently-active KC fraction, enforced structurally via top-k rather than simulating the real APL feedback-inhibition neuron) | `run_steering.py (KC_SPARSITY)` |
| `trace_decay` | `60.0` | 60.0-120.0 | measured (docs/TRACE_BIOLOGY.md, Handler et al. 2019, Cell: KC->MBON synaptic-tag plasticity is significant at ISIs of -1.2s/0s/+0.5s, a ~1-2s window, and negligible by 6s -- 60 frames = 1s at 60Hz sits at that window's near edge, and the range is the window itself, 60-120 frames) | `run_steering.py (TRACE_DECAY)` |
| `learning_rate` | `0.001` | unknown | invented (checked against a hand-computed dW on a real KC->MBON weight: one full punishment depresses an eligible synapse by 5%) | `run_steering.py (LEARNING_RATE)` |
| `mbon_dna02_frac_l` | `0.00379` | unknown | measured (docs/RUNS.md run 014: a raw synapse-COUNT fraction computed against the real mushroom-body connectome, not a sweep or a published timescale -- the closest existing provenance bucket, not a perfect fit; run 020 found the shipped code applied it unsigned/excitatory when the MBON's real dominant partners are GABAergic, fixed in run 021; 014's own finding that this bias is ~4,000x too small to matter still stands) | `bridge/full_policy.py (MBON_DNA02_FRAC['L'])` |
| `mbon_dna02_frac_r` | `0.00632` | unknown | measured (docs/RUNS.md run 014, same derivation and caveats as mbon_dna02_frac_l) | `bridge/full_policy.py (MBON_DNA02_FRAC['R'])` |
| `n_mb_sensory` | `7` | unknown | invented (docs/CODE_AUDIT.md section H: the KC projection's input vector dimensionality -- theta_L, theta_R, odor_l_eff, odor_r_eff, gap_w, mb_prev_dnp09, hungry; changing this changes the shape of mb_proj, not just a gain) | `bridge/full_policy.py (N_MB_SENSORY)` |
| `kc_features_per_cell` | `3` | unknown | invented (docs/CODE_AUDIT.md section H: how many of the n_mb_sensory features each Kenyon cell samples -- an architecture choice, matched loosely to the real fly's KC claw count, not measured against this connectome) | `bridge/full_policy.py (np.random.choice(N_MB_SENSORY, size=3))` |
| `kc_projection_seed` | `0` | unknown | invented (docs/CODE_AUDIT.md section H: fixes WHICH random KC projection is built once at __init__ -- "the seed is part of the golden", not a value to change casually) | `bridge/full_policy.py (np.random.default_rng(0))` |

## HabituationParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `hab_progress_px` | `16` | unknown | invented (one tile -- same "did that actually help" bar CLIMB_CLEAR_DISTANCE uses, deliberately smaller) | `fly/state/reflex_habituation.py (HAB_PROGRESS_PX)` |
| `hab_give_up` | `3` | unknown | invented (consecutive no-progress firings before a reflex suppresses itself) | `fly/state/reflex_habituation.py (HAB_GIVE_UP)` |

## OdourParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `odour_gain` | `16.0` | unknown | invented (chosen by simulating the real steering circuit end to end, scripts/tune_odour.py -- the smallest gain that makes a close (16px) encounter cross HOME_BIAS's settled output in the actual recurrent network; fixes a 40x unit mismatch, not a connectome-derived value) | `run_steering.py (ODOUR_GAIN)` |
| `hunger_mult_hungry` | `3.0` | unknown | measured (scripts/tune_odour.py sweep: smallest value that still flips the WTA at d=40px) | `bridge/perception.py (HUNGER_MULT_HUNGRY)` |
| `hunger_mult_sated` | `1.0` | unknown | invented (unboosted baseline, not zeroed) | `bridge/perception.py (HUNGER_MULT_SATED)` |
| `alpha_adapt` | `0.011111111111111112` | unknown | measured (~1.5s time constant at 60fps, the real ORN adaptation timescale asked for) | `fly/sensing/olfactory_adaptation.py (ALPHA_ADAPT)` |
| `avers_presence_gate` | `1e-06` | unknown | invented (docs/CODE_AUDIT.md section H: a numerical near-zero floor for "is there any aversive odour at all", not a claim about a real detection threshold) | `bridge/full_policy.py (avers_r_eff > 1e-6)` |

## TerrainParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `refusal_gap_tiles` | `5` | unknown | invented (mechanical body-scaled threshold, derived from prior calibration boundaries: 007's clean 0-4-tile GAP_GAIN sweep and 008/011's 8-tile failure -- "refuse anything not already shown to work", not a circuit gain) | `run_steering.py (REFUSAL_GAP_TILES)` |
| `refusal_gap_margin_tiles` | `2` | unknown | invented (docs/CODE_AUDIT.md section H: the synthetic wide-gap demo's own poke is refusal_gap_tiles PLUS this margin, so it's unambiguously wider than the refusal threshold it's testing, not a circuit gain -- exercised by tests/test_golden.py::test_017_reprise via inject_gap_frame) | `run_steering.py (poke_wide_gap's width_tiles default)` |

## InteractionParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `stomp_distance_px` | `20` | unknown | invented (docs/CODE_AUDIT.md section H: a stomp is inferred as "an enemy slot went inactive within this many px of Mario's own position" -- 20px, deliberately NOT one tile (16px, entity_width_px) -- do not "fix" this to match that; the audit explicitly flags them as different numbers for a reason no longer documented beyond "not the same value") | `bridge/full_policy.py (FullPolicy.act, abs(last_x - mario_x) < 20)` |
| `closing_speed_history_frames` | `10` | unknown | invented (docs/CODE_AUDIT.md section H: how many recent frames of distance-to-threat history the closing-speed estimate keeps) | `bridge/full_policy.py (FullPolicy.act, d_history capped at 10)` |

## EntityParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `entity_width_px` | `16` | unknown | invented (every enemy-slot entity assumed this wide for the looming-angle calculation, real Goomba/Koopa/mushroom hitboxes differ in real SMB and this project has never modelled that) | `mario/entities/registry.py (ENTITY_WIDTH_PX)` |

## RetinotopyParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `azimuth_d_ref` | `128.0` | unknown | invented (half the NES screen width, an arbitrary but stated saturation point; no principled reference distance exists in hex coordinates) | `fly/sensing/retinotopy.py (AZIMUTH_D_REF)` |
| `hex1_spread_fallback` | `3.0` | unknown | invented (fallback bandwidth for a cell with no measured hex-carrying input -- an empty case in practice; a bare literal, not a named constant) | `fly/sensing/retinotopy.py (receptive_field_centers, literal)` |
| `hex1_spread_floor` | `0.5` | unknown | invented (floor on a single-partner cell's measured spread, which would otherwise be exactly zero and make its tuning curve a delta function; a bare literal, not a named constant) | `fly/sensing/retinotopy.py (receptive_field_centers, literal)` |

## DemoParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `mushroom_offset` | `-40` | unknown | invented (spawn position for the synthetic mushroom-injection demo, behind Mario so it competes with HOME_BIAS's rightward pull) | `run_steering.py (MUSHROOM_OFFSET)` |
| `wide_gap_lead_tiles` | `10` | unknown | invented (docs/CODE_AUDIT.md section H: how many tiles ahead of Mario the synthetic wide-gap demo places its fixed gap column -- exercised by tests/test_golden.py::test_017_reprise via inject_gap_frame, not purely a demo-only value the way mushroom_offset is) | `run_steering.py (wide_gap_target_col's lead_tiles default)` |

## PagePerceptionParams

| field | value | range | provenance | home |
|---|---|---|---|---|

## GapAheadParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `perceive_tiles` | `4` | unknown | invented (perceptual range of the anticipatory gap input, mechanical, not a circuit gain; the current itself is still gap_gain x width) | `bridge/controller_modules.py (GapAheadPerceptionModule)` |

## MotorDirectParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `decay` | `0.9` | unknown | invented (per-frame decay of the motor drive, tau ~10 frames: the low-pass of a motor neuron pool; replaces jump_hold_frames/jump_cooldown_frames) | `bridge/controller_modules.py (MotorDirectModule)` |
| `a_threshold` | `0.3` | unknown | invented (A is down while the drive is above this; motor threshold, like ttmn_press_threshold) | `bridge/controller_modules.py (MotorDirectModule)` |
| `ttmn_gain` | `1.0` | unknown | invented (drive added per unit of TTMn rise, in units of the press threshold) | `bridge/controller_modules.py (MotorDirectModule)` |
| `dlmn_gain` | `0.05` | unknown | invented (drive added per frame per unit of DLMn: sustained DLMn lengthens the hold, a graded long jump instead of the binary choice) | `bridge/controller_modules.py (MotorDirectModule)` |

## MbonReadoutParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `dnp01_frac` | `0.005` | unknown | invented (same order as mbon_dna02_frac_*) | `bridge/controller_modules.py (MbonReadoutModule)` |
| `dlmn_frac` | `0.005` | unknown | invented (same order as mbon_dna02_frac_*) | `bridge/controller_modules.py (MbonReadoutModule)` |
| `dnp09_frac` | `0.005` | unknown | invented (same order as mbon_dna02_frac_*) | `bridge/controller_modules.py (MbonReadoutModule)` |
| `mdn_frac` | `0.005` | unknown | invented (same order as mbon_dna02_frac_*) | `bridge/controller_modules.py (MbonReadoutModule)` |


## Totals

**71 hand-set scalars.** Three (`RetinotopyParams`) are dormant; three
more (`DemoParams.mushroom_offset`, `DemoParams.wide_gap_lead_tiles`,
`TerrainParams.refusal_gap_margin_tiles`) only matter in an opt-in
injection demo -- the first is untested by any golden, the other two are
exercised by `tests/test_golden.py::test_017_reprise`'s own
`inject_gap_frame`, so "opt-in" here means "off by default", not
"untested". The other 65 are live in every default run.

A range of `unknown` means genuinely unknown, not left blank: an invented
bound would be scaffolding that looks like data. Only `JumpParams.g` and
`NoiseParams.sigma` have a characterised range.

By category (the first word of each provenance): **49 invented**, **22 measured**, **0 connectome-derived** (of 71).

None are connectome-derived. The connectome determines each circuit's
weight matrix `W`; every scalar here sits outside it, as a gain on it, a
threshold on its output, or a mechanical hold with no neural meaning.
"Measured" means simulated against the real `W` and picked by a sweep, or
matched to a published biological timescale.

Three fields are marked `advanced` in their own metadata (not shown in
the table above, checked via `field.metadata["advanced"]`):
`MushroomBodyParams.n_mb_sensory`, `.kc_features_per_cell`,
`.kc_projection_seed` -- an architecture dimension and a seed the golden
depends on bit-for-bit, not a gain like the rest of this table.
