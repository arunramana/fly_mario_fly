# What this file does, in plain English:
# The single list of every hand-picked number in the brain model (strengths,
# thresholds, how long a button is held, and so on), grouped by the part it
# belongs to. Each number carries its value, a known range if there is one,
# a note on where it came from (for example invented or measured), and where
# in the code it is used. docs/SCALARS.md is generated from this file.
"""config/params.py -- every hand-set scalar, one frozen dataclass per
component (REFACTOR_PLAN.md section 5.3).

Each field carries its value, a range (None = genuinely unknown; an
invented bound would be scaffolding that looks like data), a provenance
whose first word is its category (invented / measured / connectome-
derived), and its live home. docs/SCALARS.md is generated from this file.

Most live modules alias their constants from here (`G = JumpParams().g`).
A few (dynamics.py, reflex_habituation.py, registry.py, retinotopy.py) keep
their own definitions because diagnostic scripts import them directly; the
dataclasses marked "reference" below document those, and
tests/test_params_match_live.py checks every value against the live one.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

Range = tuple[float, float] | None


def _f(default, range: Range, provenance: str, home: str, advanced: bool = False):
    """`advanced=True`: not a circuit gain in the usual sense (an
    architecture dimension or a seed the golden depends on bit-for-bit,
    docs/CODE_AUDIT.md section H) -- tracked and reproducible the same as
    every other field, but flagged so a future UI can put it in its own
    section instead of alongside `jump.g`."""
    return field(default=default, metadata={
        "range": range, "provenance": provenance, "home": home, "advanced": advanced,
    })


# ---- fly/network/dynamics.py, shared by every circuit --------------------

@dataclass(frozen=True)
class NetworkParams:
    """Reference for dynamics.py's own module constants."""
    alpha: float = _f(0.3, None, "measured (spec-level, sprint 1: leak time constant ~= 1/alpha substeps)",
                       "fly/network/dynamics.py (ALPHA)")
    clip: float = _f(50.0, None, "invented (spec-level, sprint 1: arbitrary firing-rate ceiling)",
                      "fly/network/dynamics.py (CLIP)")
    substeps: int = _f(10, None, "measured (spec-level, sprint 1: 60fps frame = 16.7ms, ~1.67ms/substep)",
                        "fly/network/dynamics.py (SUBSTEPS)")
    denormal_flush_threshold: float = _f(1e-30, None,
                                           "invented (docs/CODE_AUDIT.md section H: numerical hygiene -- "
                                           "anything below this is flushed to exactly 0.0 so subnormal "
                                           "floats don't slow the matvec; not a claim about a real "
                                           "biological floor. The jump circuit deliberately does NOT call "
                                           "flush_denormals -- CLAUDE.md's own GPU section: fixing that "
                                           "re-baselines every golden and needs its own dedicated sprint)",
                                           "fly/network/network.py (Network.flush_denormals's own default) "
                                           "and bridge/full_policy.py's h_mbon inline flush")


@dataclass(frozen=True)
class NoiseParams:
    """sigma is a per-call argument (run_steering.main(sigma=...)), but as
    hand-set as anything else here."""
    sigma: float = _f(0.0, (0.04, 0.06),
                       "measured (025's calibration sweep: smallest sigma giving a whole-frame "
                       "commitment-time spread across 50 seeds while DNp01 still commits in "
                       "every episode; 0.07+ is a qualitatively different, pathway-failing regime)",
                       "run_steering.py main()'s sigma= default")


# ---- the six circuits (fly/network/network.py Network instances) ---------

@dataclass(frozen=True)
class JumpParams:
    """DNp01/TTMn -- the original escape circuit, SPEC_jump.md."""
    g: float = _f(2.0, (1.12, 3.35),
                   "measured (scripts/diag4.py Diagnostic-4 sweep against the real 1255-neuron subgraph; "
                   "band checked robust across 5 random trace seeds)",
                   "run_mario.py (G)")
    dnp01_spike_threshold: float = _f(0.5, None,
                                        "measured (scripts/diag4.py sweep)", "run_mario.py (DNP01_SPIKE_THRESHOLD)")
    ttmn_press_threshold: float = _f(3.0, None,
                                       "measured (scripts/diag4.py sweep)", "run_mario.py (TTMN_PRESS_THRESHOLD)")
    spike_amp: float = _f(50.0, None,
                            "measured (matched to CLIP -- a spike is a full-scale event)",
                            "run_mario.py (SPIKE_AMP)")
    jump_hold_frames: int = _f(25, None,
                                 "invented (mechanical output-interface constant, not part of the "
                                 "neural model)",
                                 "run_mario.py (JUMP_HOLD_FRAMES)")
    jump_cooldown_frames: int = _f(40, None,
                                     "invented (mechanical output-interface constant)",
                                     "run_mario.py (JUMP_COOLDOWN_FRAMES)")


@dataclass(frozen=True)
class Dnp02Params:
    """DNp02 -- the second escape pathway, SPEC_second_escape.md."""
    g: float = _f(1.2, None,
                    "measured (scripts/tune_dnp02.py/scripts/tune_dnp02_widen.py, kept <=0.85x the real spectral-"
                    "radius boundary -- a per-matrix constraint, not a fixed numeric range)",
                    "run_steering.py (G_DNP02)")
    spike_threshold: float = _f(0.1, None, "measured", "run_steering.py (DNP02_SPIKE_THRESHOLD)")
    alpha: float = _f(0.1, None,
                        "invented (a slow EMA rate on DNp02's own input current, giving it "
                        "\"longer integration\" without slowing HybridState's shared alpha)",
                        "run_steering.py (DNP02_ALPHA)")


@dataclass(frozen=True)
class TakeoffParams:
    """DNp01 -> GFC1-4 -> DLMn, the pit-triggered graded long jump,
    SPEC_terrain.md sections 2-3."""
    g: float = _f(0.8, None, "measured (scripts/tune_terrain.py)", "run_steering.py (G_TAKEOFF)")
    gap_gain: float = _f(0.6, None,
                           "invented (external current per non-ground tile ahead onto DNp01 -- "
                           "no real synapse carries terrain information, same modelling category "
                           "as HOME_BIAS/WALK_DRIVE/MDN_DRIVE)",
                           "run_steering.py (GAP_GAIN)")
    dlmn_recruit_threshold: float = _f(1.0, None,
                                         "measured (scripts/tune_terrain.py: sits between the width-1 and "
                                         "width-2 DLMn end-of-frame means)",
                                         "run_steering.py (DLMN_RECRUIT_THRESHOLD)")
    long_jump_hold_frames: int = _f(35, None, "invented (mechanical output-interface constant)",
                                      "run_steering.py (LONG_JUMP_HOLD_FRAMES)")
    gap_lookahead_tiles: int = _f(8, None,
                                    "invented (perceptual range, mechanical, not a circuit gain)",
                                    "run_steering.py (GAP_LOOKAHEAD_TILES)")
    # docs/SPEC_pits.md, opt-in behind config.scenario.graded_pit_response
    # (False keeps every golden byte-identical -- see that flag's own
    # docstring in config/project_config.py).
    long_jump_trigger_distance_tiles: int = _f(2, None,
                                                 "invented (mechanical launch-distance threshold: "
                                                 "docs/SPEC_pits.md's own validation found the ORIGINAL "
                                                 "threshold-only trigger firing only once the shared "
                                                 "jump_cooldown/jump_hold timer happened to reopen, by "
                                                 "which point Mario's own column had already advanced 2 "
                                                 "of a 3-tile pit's own footprint -- 2 tiles of solid "
                                                 "ground still ahead gives the 35-frame hold's arc "
                                                 "somewhere to land)",
                                                 "bridge/full_policy.py (FullPolicy.act's gap_override)")
    run_up_tiles: int = _f(4, None,
                             "invented (mechanical run-up distance: wider than "
                             "long_jump_trigger_distance_tiles so B is already held by the time the "
                             "jump itself launches -- a NES running jump clears more horizontal "
                             "distance than a standing one)",
                             "bridge/full_policy.py (FullPolicy.act's press_b override)")


@dataclass(frozen=True)
class SpeedParams:
    """DNp09, the walk/stop gate, SPEC_terrain.md."""
    g: float = _f(1.2, None, "measured (scripts/tune_terrain.py)", "run_steering.py (G_SPEED)")
    walk_drive: float = _f(1.0, None,
                             "invented (constant \"walk\" current, no real synapse carries it)",
                             "run_steering.py (WALK_DRIVE)")
    walk_suppression: float = _f(1.0, None,
                                   "invented (cancels WALK_DRIVE while jumping/stalled)",
                                   "run_steering.py (WALK_SUPPRESSION)")
    dnp09_speed_threshold: float = _f(0.5, None, "measured",
                                        "run_steering.py (DNP09_SPEED_THRESHOLD)")


@dataclass(frozen=True)
class SteeringParams:
    """DNa01/DNa02 home-bias-vs-odour WTA plus the contact-based climb
    reflex, SPEC_steering.md."""
    g: float = _f(1.2, None, "measured (scripts/tune_steering.py)", "run_steering.py (G_STEER)")
    home_bias: float = _f(1.0, None,
                            "invented (constant \"go home\" current, R-hemisphere only; no real "
                            "synapse carries it -- explicitly a placed bias, not a scaling error "
                            "to fix by lowering it, per SPEC_odour.md section 0)",
                            "run_steering.py (HOME_BIAS)")
    climb_stall_frames: int = _f(20, None,
                                   "invented (mechanical: mario_x unchanged this long while "
                                   "steering=R -> blocked)",
                                   "run_steering.py (CLIMB_STALL_FRAMES)")
    climb_hop_small_frames: int = _f(10, None, "invented (mechanical, small Mario's first-try hop)",
                                       "run_steering.py (CLIMB_HOP_SMALL_FRAMES)")
    climb_hop_big_frames: int = _f(14, None, "invented (mechanical, big Mario's taller hitbox)",
                                     "run_steering.py (CLIMB_HOP_BIG_FRAMES)")
    climb_jump_frames: int = _f(25, None,
                                  "invented (mechanical, same magnitude as the escape jump hold)",
                                  "run_steering.py (CLIMB_JUMP_FRAMES)")
    climb_cooldown_frames: int = _f(15, None, "invented (mechanical)",
                                      "run_steering.py (CLIMB_COOLDOWN_FRAMES)")
    climb_clear_distance: int = _f(24, None,
                                     "invented (mechanical, px of forward progress that resets the "
                                     "attempt counter)",
                                     "run_steering.py (CLIMB_CLEAR_DISTANCE)")


@dataclass(frozen=True)
class MdnParams:
    """MDN, the backward-walking escape-habituation fallback,
    SPEC_habituation.md section 2."""
    g: float = _f(1.2, None,
                    "measured (scripts/tune_mdn.py: real spectral radius 0.7345, comfortably under its "
                    "~1.36 linear boundary)",
                    "run_steering.py (G_MDN)")
    mdn_drive: float = _f(2.0, None,
                            "invented (external current -- no real DNp01/GFC1-4 synapse onto MDN "
                            "in this connectome, checked)",
                            "run_steering.py (MDN_DRIVE)")
    mdn_threshold: float = _f(1.0, None, "measured (scripts/tune_mdn.py)",
                                "run_steering.py (MDN_THRESHOLD)")
    mdn_backup_frames: int = _f(30, None,
                                  "invented (mechanical, fixed-duration corrective backup)",
                                  "run_steering.py (MDN_BACKUP_FRAMES)")


@dataclass(frozen=True)
class MushroomBodyParams:
    """KC/MBON/DAN three-factor plasticity, SPEC_mushroom_body.md."""
    kc_sparsity: float = _f(0.05, None,
                              "measured (matches the real fly's ~5% concurrently-active KC "
                              "fraction, enforced structurally via top-k rather than simulating "
                              "the real APL feedback-inhibition neuron)",
                              "run_steering.py (KC_SPARSITY)")
    trace_decay: float = _f(60.0, (60.0, 120.0),
                              "measured (docs/TRACE_BIOLOGY.md, Handler et al. 2019, Cell: "
                              "KC->MBON synaptic-tag plasticity is significant at ISIs of "
                              "-1.2s/0s/+0.5s, a ~1-2s window, and negligible by 6s -- 60 "
                              "frames = 1s at 60Hz sits at that window's near edge, and the "
                              "range is the window itself, 60-120 frames)",
                              "run_steering.py (TRACE_DECAY)")
    learning_rate: float = _f(0.001, None,
                                "invented (checked against a hand-computed dW on a real KC->MBON "
                                "weight: one full punishment depresses an eligible synapse by 5%)",
                                "run_steering.py (LEARNING_RATE)")
    recovery_rate: float = _f(0.0, (0.0, 1.0),
                                "invented (docs/SPEC_learning_v3.md A1: strength of recovery toward the untrained weight "
                                "per unit of dopamine at KCs that were not recently active; 0 = off, depression only)",
                                "fly/plasticity/three_factor.py (recover)")
    mbon_dna02_frac_l: float = _f(0.00379, None,
                                    "measured (docs/RUNS.md run 014: a raw synapse-COUNT fraction "
                                    "computed against the real mushroom-body connectome, not a sweep "
                                    "or a published timescale -- the closest existing provenance "
                                    "bucket, not a perfect fit; run 020 found the shipped code applied "
                                    "it unsigned/excitatory when the MBON's real dominant partners are "
                                    "GABAergic, fixed in run 021; 014's own finding that this bias is "
                                    "~4,000x too small to matter still stands)",
                                    "bridge/full_policy.py (MBON_DNA02_FRAC['L'])")
    mbon_dna02_frac_r: float = _f(0.00632, None,
                                    "measured (docs/RUNS.md run 014, same derivation and caveats as "
                                    "mbon_dna02_frac_l)",
                                    "bridge/full_policy.py (MBON_DNA02_FRAC['R'])")
    n_mb_sensory: int = _f(7, None,
                             "invented (docs/CODE_AUDIT.md section H: the KC projection's input "
                             "vector dimensionality -- theta_L, theta_R, odor_l_eff, odor_r_eff, "
                             "gap_w, mb_prev_dnp09, hungry; changing this changes the shape of "
                             "mb_proj, not just a gain)",
                             "bridge/full_policy.py (N_MB_SENSORY)", advanced=True)
    kc_features_per_cell: int = _f(3, None,
                                     "invented (docs/CODE_AUDIT.md section H: how many of the "
                                     "n_mb_sensory features each Kenyon cell samples -- an "
                                     "architecture choice, matched loosely to the real fly's KC "
                                     "claw count, not measured against this connectome)",
                                     "bridge/full_policy.py (np.random.choice(N_MB_SENSORY, size=3))",
                                     advanced=True)
    kc_projection_seed: int = _f(0, None,
                                   "invented (docs/CODE_AUDIT.md section H: fixes WHICH random KC "
                                   "projection is built once at __init__ -- \"the seed is part of "
                                   "the golden\", not a value to change casually)",
                                   "bridge/full_policy.py (np.random.default_rng(0))", advanced=True)


# ---- fly/state/ habituation ----------------------------------------------

@dataclass(frozen=True)
class HabituationParams:
    """SPEC_habituation.md section 1. Reference for reflex_habituation.py."""
    hab_progress_px: int = _f(16, None,
                                "invented (one tile -- same \"did that actually help\" bar "
                                "CLIMB_CLEAR_DISTANCE uses, deliberately smaller)",
                                "fly/state/reflex_habituation.py (HAB_PROGRESS_PX)")
    hab_give_up: int = _f(3, None,
                            "invented (consecutive no-progress firings before a reflex "
                            "suppresses itself)",
                            "fly/state/reflex_habituation.py (HAB_GIVE_UP)")


# ---- odour: bridge/perception.py + fly/sensing/olfactory_adaptation.py ----

@dataclass(frozen=True)
class OdourParams:
    """SPEC_odour.md. One pipeline across two files: raw concentration ->
    gain/hunger -> adaptation."""
    odour_gain: float = _f(16.0, None,
                             "invented (chosen by simulating the real steering circuit end to "
                             "end, scripts/tune_odour.py -- the smallest gain that makes a close (16px) "
                             "encounter cross HOME_BIAS's settled output in the actual recurrent "
                             "network; fixes a 40x unit mismatch, not a connectome-derived value)",
                             "run_steering.py (ODOUR_GAIN)")
    hunger_mult_hungry: float = _f(3.0, None,
                                     "measured (scripts/tune_odour.py sweep: smallest value that still "
                                     "flips the WTA at d=40px)",
                                     "bridge/perception.py (HUNGER_MULT_HUNGRY)")
    hunger_mult_sated: float = _f(1.0, None, "invented (unboosted baseline, not zeroed)",
                                    "bridge/perception.py (HUNGER_MULT_SATED)")
    alpha_adapt: float = _f(1.0 / 90.0, None,
                              "measured (~1.5s time constant at 60fps, the real ORN adaptation "
                              "timescale asked for)",
                              "fly/sensing/olfactory_adaptation.py (ALPHA_ADAPT)")
    avers_presence_gate: float = _f(1e-6, None,
                                      "invented (docs/CODE_AUDIT.md section H: a numerical "
                                      "near-zero floor for \"is there any aversive odour at all\", "
                                      "not a claim about a real detection threshold)",
                                      "bridge/full_policy.py (avers_r_eff > 1e-6)")


# ---- terrain / refusal ---------------------------------------------------

@dataclass(frozen=True)
class TerrainParams:
    refusal_gap_tiles: int = _f(5, None,
                                  "invented (mechanical body-scaled threshold, derived from prior "
                                  "calibration boundaries: 007's clean 0-4-tile GAP_GAIN sweep and "
                                  "008/011's 8-tile failure -- \"refuse anything not already shown "
                                  "to work\", not a circuit gain)",
                                  "run_steering.py (REFUSAL_GAP_TILES)")
    refusal_gap_margin_tiles: int = _f(2, None,
                                         "invented (docs/CODE_AUDIT.md section H: the synthetic wide-"
                                         "gap demo's own poke is refusal_gap_tiles PLUS this margin, so "
                                         "it's unambiguously wider than the refusal threshold it's "
                                         "testing, not a circuit gain -- exercised by "
                                         "tests/test_golden.py::test_017_reprise via inject_gap_frame)",
                                         "run_steering.py (poke_wide_gap's width_tiles default)")


# ---- game-event detection (stomp, closing speed) -- not one circuit's own -

@dataclass(frozen=True)
class InteractionParams:
    """FullPolicy.act's own game-mechanic detection, not any one circuit's
    gain (docs/CODE_AUDIT.md section H)."""
    stomp_distance_px: int = _f(20, None,
                                  "invented (docs/CODE_AUDIT.md section H: a stomp is inferred as "
                                  "\"an enemy slot went inactive within this many px of Mario's own "
                                  "position\" -- 20px, deliberately NOT one tile (16px, "
                                  "entity_width_px) -- do not \"fix\" this to match that; the audit "
                                  "explicitly flags them as different numbers for a reason no longer "
                                  "documented beyond \"not the same value\")",
                                  "bridge/full_policy.py (FullPolicy.act, "
                                  "abs(last_x - mario_x) < 20)")
    closing_speed_history_frames: int = _f(10, None,
                                             "invented (docs/CODE_AUDIT.md section H: how many recent "
                                             "frames of distance-to-threat history the closing-speed "
                                             "estimate keeps)",
                                             "bridge/full_policy.py (FullPolicy.act, "
                                             "d_history capped at 10)")


# ---- mario/entities/ -----------------------------------------------------

@dataclass(frozen=True)
class EntityParams:
    """Reference for mario/entities/registry.py."""
    entity_width_px: int = _f(16, None,
                                "invented (every enemy-slot entity assumed this wide for the "
                                "looming-angle calculation, real Goomba/Koopa/mushroom hitboxes "
                                "differ in real SMB and this project has never modelled that)",
                                "mario/entities/registry.py (ENTITY_WIDTH_PX)")


# ---- fly/sensing/retinotopy.py: dormant, closed negative result ----------

@dataclass(frozen=True)
class RetinotopyParams:
    """Reference for retinotopy.py. Inactive in every default run
    (retinotopic=False)."""
    azimuth_d_ref: float = _f(128.0, None,
                                "invented (half the NES screen width, an arbitrary but stated "
                                "saturation point; no principled reference distance exists in "
                                "hex coordinates)",
                                "fly/sensing/retinotopy.py (AZIMUTH_D_REF)")
    hex1_spread_fallback: float = _f(3.0, None,
                                       "invented (fallback bandwidth for a cell with no measured "
                                       "hex-carrying input -- an empty case in practice; a bare "
                                       "literal, not a named constant)",
                                       "fly/sensing/retinotopy.py (receptive_field_centers, literal)")
    hex1_spread_floor: float = _f(0.5, None,
                                    "invented (floor on a single-partner cell's measured spread, "
                                    "which would otherwise be exactly zero and make its tuning "
                                    "curve a delta function; a bare literal, not a named constant)",
                                    "fly/sensing/retinotopy.py (receptive_field_centers, literal)")


# ---- test/demo only: inactive in every default run -----------------------

@dataclass(frozen=True)
class DemoParams:
    """mushroom_offset only matters when a caller opts in with
    inject_frame=; no golden run does. wide_gap_lead_tiles matters
    whenever inject_gap_frame is set -- test_017_reprise does."""
    mushroom_offset: int = _f(-40, None,
                                "invented (spawn position for the synthetic mushroom-injection "
                                "demo, behind Mario so it competes with HOME_BIAS's rightward pull)",
                                "run_steering.py (MUSHROOM_OFFSET)")
    wide_gap_lead_tiles: int = _f(10, None,
                                    "invented (docs/CODE_AUDIT.md section H: how many tiles ahead "
                                    "of Mario the synthetic wide-gap demo places its fixed gap column "
                                    "-- exercised by tests/test_golden.py::test_017_reprise via "
                                    "inject_gap_frame, not purely a demo-only value the way "
                                    "mushroom_offset is)",
                                    "run_steering.py (wide_gap_target_col's lead_tiles default)")


# ---- controller modules (bridge/controller_modules.py) -------------------
# One frozen params dataclass per module; a module is ON because its field
# in ModulesConfig is set, OFF (None) by default. Not in ALL_PARAM_CLASSES
# (tool/core/schema.py maps every entry there to a direct ProjectConfig
# field); counted and documented via MODULE_PARAM_CLASSES instead.

@dataclass(frozen=True)
class PagePerceptionParams:
    """bridge/controller_modules.py's PagePerceptionModule (PERCEPTION). Presence in
    ModulesConfig switches on page-aware distances; `ignore_behind` additionally drops enemies
    behind Mario from the looming input (docs/SPEC_learning_v3.md A4)."""
    ignore_behind: bool = _f(False, None,
        "invented (perception: an enemy behind Mario is outside the frontal visual field and "
        "produces no looming; off = theta from |d| for enemies on both sides, today's behaviour)",
        "bridge/perception.py (enemy_thetas)")


@dataclass(frozen=True)
class GapAheadParams:
    """bridge/controller_modules.py's GapAheadPerceptionModule (PERCEPTION)."""
    perceive_tiles: int = _f(4, None,
        "invented (perceptual range of the anticipatory gap input, mechanical, not a circuit "
        "gain; the current itself is still gap_gain x width)",
        "bridge/controller_modules.py (GapAheadPerceptionModule)")


@dataclass(frozen=True)
class Dnp02RefractoryParams:
    """bridge/controller_modules.py's Dnp02RefractoryModule (CIRCUIT). Gives
    the DNp02 spiking cells an absolute refractory period. In the real DNp02
    subgraph DNp02 R -> pIP1 R (0.876) -> DNp02 R (0.0244) closes a loop whose
    feedback drive (1.465 per step at saturation) is 4.4x what re-fires
    DNp02 (threshold/alpha = 0.33), so one spike latches the pathway on for
    the rest of the run; the refractory period lets pIP1 decay between spikes
    (it needs >= ~5 steps to fall below the ~11 that still sustains the loop)."""
    refractory_steps: int = _f(8, (1, 50),
        "invented (absolute refractory period of the DNp02 spiking cells, in network substeps: "
        "10 substeps = 1 frame = 16.7 ms; must exceed ~5 for pIP1 to decay below the level "
        "that re-fires DNp02)", "fly/network/integrator.py (refractory_steps)")


@dataclass(frozen=True)
class Dnp01RefractoryParams:
    """bridge/controller_modules.py's Dnp01RefractoryModule (CIRCUIT): the
    same absolute refractory period as Dnp02RefractoryParams, applied to the
    jump circuit's DNp01 (Giant Fiber) spiking cells. A separate toggle: the
    two pathways are separate networks and are switched independently."""
    refractory_steps: int = _f(8, (1, 50),
        "invented (absolute refractory period of the DNp01 spiking cells, in network substeps: "
        "10 substeps = 1 frame = 16.7 ms)", "fly/network/integrator.py (refractory_steps)")


@dataclass(frozen=True)
class ArousalParams:
    """bridge/controller_modules.py's ArousalModule (CIRCUIT), docs/
    SPEC_arousal_pc1.md: a steady drive into the pC1 arousal population,
    delivered to each circuit through pC1's real synapses (share of the target's
    total input). arousal 0 = no injection at all (behaviour identical)."""
    arousal: float = _f(0.0, (0.0, 1.0),
        "invented (the Character-tab slider: 0 = off, 1 = pC1 at arousal_max_h; a state, like "
        "hunger, not a gain on a circuit)", "bridge/full_policy.py (arousal)")
    arousal_max_h: float = _f(10.0, (0.0, 50.0),
        "invented (pC1 activity, in network h units, at arousal 1; 50 is the network clip)",
        "bridge/full_policy.py (arousal_max_h)")
    two_hop: bool = _f(False, None,
        "invented (mechanical: also drive through one intermediate neuron, Dale-signed; "
        "off = direct pC1 synapses only)", "fly/circuits/pc1_arousal_weights.py (two_hop)")


@dataclass(frozen=True)
class WallAheadParams:
    """bridge/controller_modules.py's WallAheadPerceptionModule (PERCEPTION).
    The first solid obstacle ahead (pipe, stair, block stack), read from the
    tile RAM as distance and height, is fed to the circuit as a stimulus only:
    an expanding object for LC4/LPLC2 (theta = 2*arctan(h / (2*d)), h = the
    obstacle's height in px) and/or a takeoff current onto DNp01. Which of the
    two carries it is set by their gains; 0 turns that route off."""
    perceive_tiles: int = _f(6, None,
        "invented (perceptual range of the wall stimulus in tiles, mechanical, not a circuit gain)",
        "bridge/controller_modules.py (WallAheadPerceptionModule)")
    looming_gain: float = _f(1.0, None,
        "invented (scale on the wall's theta/dtheta into LC4/LPLC2, the same stimulus class as an "
        "enemy's looming; 0 = the looming route is off)",
        "bridge/controller_modules.py (WallAheadPerceptionModule)")
    takeoff_gain: float = _f(0.0, None,
        "invented (current onto DNp01 per tile of wall height, scaled up as the wall approaches like "
        "gap_ahead; 0 = the takeoff route is off)",
        "bridge/controller_modules.py (WallAheadPerceptionModule)")


@dataclass(frozen=True)
class MbSpatialInputParams:
    """bridge/controller_modules.py's MbSpatialInputModule (PERCEPTION). No
    scalars: presence in ModulesConfig adds two Kenyon-cell inputs -- how
    close the next pit edge is and how close the nearest enemy ahead is
    (page-corrected) -- so the mushroom body can learn *where* danger is,
    not only that a gap or looming exists."""


@dataclass(frozen=True)
class QBlockAheadParams:
    """bridge/controller_modules.py's QBlockAheadPerceptionModule (PERCEPTION).
    Unhit `?` blocks at or ahead of Mario, read from the tile RAM as distance
    and height, reach the circuit only as stimuli: two extra Kenyon-cell inputs
    (closeness and height, 0..1) and, if `looming_gain` > 0, a weak looming
    cue for a block ahead. Never a jump command (docs/SPEC_learning_v2.md
    section 5)."""
    perceive_tiles: int = _f(8, None,
        "invented (perceptual range of the ? block cue in tiles, mechanical, not a circuit gain)",
        "bridge/controller_modules.py (QBlockAheadPerceptionModule)")
    looming_gain: float = _f(0.0, None,
        "invented (scale on the ? block's looming angle theta into LC4/LPLC2, the same stimulus "
        "class as an enemy's or a wall's; 0 = the looming route is off)",
        "bridge/controller_modules.py (QBlockAheadPerceptionModule)")


@dataclass(frozen=True)
class MbGapSpeedInputParams:
    """bridge/controller_modules.py's MbGapSpeedInputModule (PERCEPTION): two more Kenyon-cell
    inputs, the width of the next pit and Mario's own horizontal speed (docs/SPEC_learning_v3.md A2)."""
    perceive_tiles: int = _f(8, None,
        "invented (how many tiles ahead the pit-width input looks; mechanical, not a circuit gain)",
        "bridge/controller_modules.py (MbGapSpeedInputModule)")


@dataclass(frozen=True)
class MotorDirectParams:
    """bridge/controller_modules.py's MotorDirectModule: A follows a leaky
    integrator of the motor neurons' own activity instead of fixed hold and
    cooldown counters."""
    decay: float = _f(0.9, None,
        "invented (per-frame decay of the motor drive, tau ~10 frames: the low-pass of "
        "a motor neuron pool; replaces jump_hold_frames/jump_cooldown_frames)",
        "bridge/controller_modules.py (MotorDirectModule)")
    a_threshold: float = _f(0.3, None,
        "invented (A is down while the drive is above this; motor threshold, like "
        "ttmn_press_threshold)", "bridge/controller_modules.py (MotorDirectModule)")
    ttmn_gain: float = _f(1.0, None,
        "invented (drive added per unit of TTMn rise, in units of the press threshold)",
        "bridge/controller_modules.py (MotorDirectModule)")
    dlmn_gain: float = _f(0.05, None,
        "invented (drive added per frame per unit of DLMn: sustained DLMn lengthens the "
        "hold, a graded long jump instead of the binary choice)",
        "bridge/controller_modules.py (MotorDirectModule)")
    release_on_landing: bool = _f(True, None,
        "invented (mechanical: A is released for one frame when Mario lands, RAM 0x001D back to 0, "
        "so the next jump is a fresh button press -- the NES only jumps on a new press)",
        "bridge/controller_modules.py (MotorDirectModule)")
    adapt_frames: float = _f(0.0, (0.0, 600.0),
        "invented (muscle adaptation, docs/SPEC_learning_v3.md A4: a TTMn rise is measured above a slow "
        "baseline with this time constant in frames, so a sustained limit cycle stops holding A; 0 = off)",
        "bridge/controller_modules.py (MotorDirectModule)")
    buttons: bool = _f(False, None,
        "invented (mode switch: the Down / Up / Left muscles below drive their buttons; off = only A, B "
        "and the steering direction, today's behaviour)", "bridge/controller_modules.py (MotorDirectModule)")
    button_decay: float = _f(0.8, None,
        "invented (per-frame decay of the Down/Up/Left muscle drives, tau ~5 frames)",
        "bridge/controller_modules.py (MotorDirectModule)")
    down_gain: float = _f(1.0, None, "invented (drive added per unit of DNp03/DNp06/DNp11 activity)",
        "bridge/controller_modules.py (MotorDirectModule)")
    down_threshold: float = _f(5.0, None,
        "invented (Down is held while its drive is at or above this; measured on learn_1: posture Down-DN "
        "activity median 0.19, peak 1.5, so a drive (~5x activity) of 5 needs a strong sustained looming)", "bridge/controller_modules.py (MotorDirectModule)")
    up_gain: float = _f(1.0, None, "invented (drive added per unit of DNg40/DNp05 activity)",
        "bridge/controller_modules.py (MotorDirectModule)")
    up_threshold: float = _f(3.0, None, "invented (Up threshold; Up-DN activity peaks at 0.76 on learn_1)",
        "bridge/controller_modules.py (MotorDirectModule)")
    left_gain: float = _f(1.0, None,
        "invented (drive added per unit of the DNa01/DNa02 left-minus-right team activity)",
        "bridge/controller_modules.py (MotorDirectModule)")
    left_threshold: float = _f(2.0, None,
        "invented (Left replaces Right while its drive is at or above this)",
        "bridge/controller_modules.py (MotorDirectModule)")
    posture_g: float = _f(0.8, None,
        "measured (spectral radius of the posture circuit is 0.9993 at g=1, so 0.8 stays stable)",
        "bridge/full_policy.py (posture network)")


@dataclass(frozen=True)
class MbonReadoutParams:
    """bridge/controller_modules.py's MbonReadoutModule: per-MBON weights onto
    each motor pathway (from the real MBON -> X -> target connectome counts)
    instead of one scalar MBON mean. Fractions are current per unit of the
    weighted MBON mean; the negative sign matches the existing DNa02 path."""
    dnp01_frac: float = _f(0.005, (0.0, 1.0), "invented (same order as mbon_dna02_frac_*)",
                           "bridge/controller_modules.py (MbonReadoutModule)")
    dlmn_frac: float = _f(0.005, (0.0, 1.0), "invented (same order as mbon_dna02_frac_*)",
                          "bridge/controller_modules.py (MbonReadoutModule)")
    dnp09_frac: float = _f(0.005, (0.0, 1.0), "invented (same order as mbon_dna02_frac_*)",
                           "bridge/controller_modules.py (MbonReadoutModule)")
    mdn_frac: float = _f(0.005, (0.0, 1.0), "invented (same order as mbon_dna02_frac_*)",
                         "bridge/controller_modules.py (MbonReadoutModule)")


@dataclass(frozen=True)
class ControlRules:
    """One switch per hand-coded control rule in docs/CONTROL_AUDIT.md that
    decides when or how long to act. True = the rule is active (today's
    behaviour, every golden unchanged); False = the rule is removed and the
    circuit alone decides. Mode flags, not tuned scalars, so they are not in
    ALL_PARAM_CLASSES (like scenario.graded_pit_response, the switch for the
    forced GradedPitModule, audit row 17). Audit row 9 (shared A button) has no
    switch: it only merges rows 1 and 7, and is vacuous with both off."""
    jump_hold: bool = True            # row 1: fixed A-hold after a commit
    jump_cooldown: bool = True        # row 2: no new commit for N frames after a jump
    long_jump_select: bool = True     # row 3: binary long-vs-short hold from one DLMn sample
    escape_habituation: bool = True   # row 4: give-up suppression of the escape reflex
    mdn_backup: bool = True           # row 5: forced backing-up hold when MDN crosses threshold
    climb_stall: bool = True          # row 6: "blocked" inferred from mario_x unchanged
    climb_reflex: bool = True         # row 7: fixed hop/jump hold, cooldown, attempt counter
    climb_habituation: bool = True    # row 8: give-up on repeated futile climbs
    refusal: bool = True              # row 10: wide-gap refusal (drops gap current, steers away, zeroes DNp09)
    walk_suppression: bool = True     # row 11: cut DNp09 drive while busy
    odour_brake: bool = True          # row 12: odour subtracted from the walk drive


CONTROL_RULE_LABELS: dict[str, str] = {
    "jump_hold": "Jump hold (fixed A-hold after a commit) -- audit row 1",
    "jump_cooldown": "Jump cooldown (no commit for N frames after a jump) -- row 2",
    "long_jump_select": "Binary long-jump selection (one DLMn sample) -- row 3",
    "escape_habituation": "Escape habituation give-up -- row 4",
    "mdn_backup": "MDN backup hold (forced backing up) -- row 5",
    "climb_stall": "Climb stall detector (mario_x unchanged) -- row 6",
    "climb_reflex": "Climb hop/jump hold, cooldown, attempt counter -- rows 7",
    "climb_habituation": "Climb habituation give-up -- row 8",
    "refusal": "Refusal rule (wide gap) -- row 10",
    "walk_suppression": "Walk suppression while busy -- row 11",
    "odour_brake": "Odour brake on the walk drive -- row 12",
}
assert set(CONTROL_RULE_LABELS) == {f.name for f in fields(ControlRules)}


@dataclass(frozen=True)
class ModulesConfig:
    """Field order is execution order; None == module off."""
    page_perception: PagePerceptionParams | None = None
    gap_ahead: GapAheadParams | None = None
    wall_ahead: WallAheadParams | None = None
    motor_direct: MotorDirectParams | None = None
    mb_spatial_inputs: MbSpatialInputParams | None = None
    dnp02_refractory: Dnp02RefractoryParams | None = None
    dnp01_refractory: Dnp01RefractoryParams | None = None
    arousal: ArousalParams | None = None
    mbon_readout: MbonReadoutParams | None = None
    qblock_ahead: QBlockAheadParams | None = None
    mb_gap_speed_inputs: MbGapSpeedInputParams | None = None


MODULE_PARAM_CLASSES: tuple = (PagePerceptionParams, GapAheadParams, WallAheadParams, MotorDirectParams, MbonReadoutParams,
                                     MbSpatialInputParams, Dnp02RefractoryParams,
                                     Dnp01RefractoryParams, ArousalParams, QBlockAheadParams,
                                     MbGapSpeedInputParams)

ALL_PARAM_CLASSES = (
    NetworkParams, NoiseParams, JumpParams, Dnp02Params, TakeoffParams, SpeedParams,
    SteeringParams, MdnParams, MushroomBodyParams, HabituationParams, OdourParams,
    TerrainParams, InteractionParams, EntityParams, RetinotopyParams, DemoParams,
)


def scalar_count() -> int:
    """Every field on every dataclass above (docs/SCALARS.md)."""
    return sum(len(fields(cls)) for cls in ALL_PARAM_CLASSES + MODULE_PARAM_CLASSES)
