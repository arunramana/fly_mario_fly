"""config/params.py -- REFACTOR_PLAN.md section 5.3/6, phase 4.

One frozen dataclass per component, each field typed with a default that
matches today's value EXACTLY (verified by tests/test_params_match_live.py
against the actual live module constants, not just asserted here) plus a
documented range or an explicit `None` where no range is known. Per this
phase's own instruction: an invented bound is scaffolding that looks like
data, so a field with `range=None` means genuinely unknown, not "the
author didn't get to it."

`ProjectConfig` (project_config.py) composes every dataclass below and
exists ONLY to compose/serialise -- per section 5.3, no component here
receives more than its own params.

This phase does NOT rewire every call site in run_steering.py/run_mario.py
to accept an injected params object -- that thread-the-config-through-the-
whole-call-graph work is phase 5's "ProjectConfig drives a run" (section 7),
not phase 4's "give every constant exactly one home." What this phase DOES
do: each live module's own top-of-file constant becomes an alias to a field
on the dataclass below (`G = JumpParams().g`, not a second, independent
`G = 2.0`), so the dataclass is the actual source of the value, not just a
document describing it. See docs/RUNS.md's phase 4 note for the modules
deliberately NOT rewired this way (dynamics.py, tile_ram.py, mario/ram/
addresses.py, mario/entities/registry.py's ENTITY_WIDTH_PX) and why:
they're widely reused by diagnostic scripts outside the live path, and
rewiring their own definition to import config/ would be a real, separate
risk for a rename-only change. Their dataclasses below are the documented
reference, checked equal to the live constant by the same test, without
the live module importing config/.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

Range = tuple[float, float] | None


def _f(default, range: Range, provenance: str, home: str, note: str | None = None):
    return field(default=default, metadata={
        "range": range, "provenance": provenance, "home": home, "note": note,
    })


# ---------------------------------------------------------------------
# fly/network/dynamics.py -- shared by all six unified circuits (phase 3)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkParams:
    """Documents dynamics.py's own module constants. NOT the live source --
    dynamics.py keeps defining these itself (see this file's own docstring
    for why: it's reused by run_mario.py's frozen demo and every
    scripts/tune_*.py / scripts/diag4.py, and importing config/ into it for a
    rename-only change isn't worth that blast radius)."""
    alpha: float = _f(0.3, None, "measured (spec-level, sprint 1: leak time constant ~= 1/alpha substeps)",
                       "fly/network/dynamics.py (ALPHA)")
    clip: float = _f(50.0, None, "invented (spec-level, sprint 1: arbitrary firing-rate ceiling)",
                      "fly/network/dynamics.py (CLIP)")
    substeps: int = _f(10, None, "measured (spec-level, sprint 1: 60fps frame = 16.7ms, ~1.67ms/substep)",
                        "fly/network/dynamics.py (SUBSTEPS)")


@dataclass(frozen=True)
class NoiseParams:
    """sigma is a per-call argument (run_steering.main(sigma=...)), not a
    module constant -- documented here anyway since it is exactly as
    "hand-set" as anything else in this file, and 025 gave it the most
    precisely characterised range of any scalar in the project."""
    sigma: float = _f(0.0, (0.04, 0.06),
                       "measured (025's calibration sweep: smallest sigma giving a whole-frame "
                       "commitment-time spread across 50 seeds while DNp01 still commits in "
                       "every episode; 0.07+ is a qualitatively different, pathway-failing regime)",
                       "run_steering.py main()'s sigma= default")


# ---------------------------------------------------------------------
# The six unified circuits (fly/network/network.py's Network instances)
# ---------------------------------------------------------------------

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
                                 "neural model, per this project's own convention since sprint 006)",
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
                        "\"longer integration\" without slowing HybridState's shared alpha -- "
                        "sprint's own bug-fix choice, not connectome-derived)",
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
                                   "steering=R -> blocked; diagnosed via A/B, see docs/RUNS.md "
                                   "sprint on habituation -- 15->40 was checked and changed nothing)",
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
                              "range is the window itself, 60-120 frames. REFACTOR_PLAN.md "
                              "phase 6's own first measured-provenance scalar grounded in a "
                              "citation to published fly biology rather than a sweep against "
                              "this project's own connectome -- the value (60) is unchanged "
                              "from before; what changed is that this is now a checked claim, "
                              "not an uncited appeal to \"the real eligibility-trace timescale\"",
                              "run_steering.py (TRACE_DECAY)")
    learning_rate: float = _f(0.001, None,
                                "invented (chosen by direct isolated verification against a hand-"
                                "computed dW on a real KC->MBON weight -- the first guess, 0.01, "
                                "was rejected on that same test as too aggressive)",
                                "run_steering.py (LEARNING_RATE)")


# ---------------------------------------------------------------------
# fly/state/ -- habituation
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class HabituationParams:
    """SPEC_habituation.md section 1. NOT the live source -- fly/state/
    reflex_habituation.py keeps defining these itself; documented here as
    the reference, checked equal by the same test as NetworkParams."""
    hab_progress_px: int = _f(16, None,
                                "invented (one tile -- same \"did that actually help\" bar "
                                "CLIMB_CLEAR_DISTANCE uses, deliberately smaller)",
                                "fly/state/reflex_habituation.py (HAB_PROGRESS_PX)")
    hab_give_up: int = _f(3, None,
                            "invented (consecutive no-progress firings before a reflex "
                            "suppresses itself)",
                            "fly/state/reflex_habituation.py (HAB_GIVE_UP)")


# ---------------------------------------------------------------------
# bridge/perception.py + fly/sensing/olfactory_adaptation.py -- odour
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class OdourParams:
    """SPEC_odour.md. Split across two files in the live code (see `home`
    per field) -- both are documented together here because they're one
    conceptual pipeline: raw concentration -> gain/hunger -> adaptation."""
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


# ---------------------------------------------------------------------
# Terrain / refusal
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class TerrainParams:
    refusal_gap_tiles: int = _f(5, None,
                                  "invented (mechanical body-scaled threshold, derived from prior "
                                  "calibration boundaries: 007's clean 0-4-tile GAP_GAIN sweep and "
                                  "008/011's 8-tile failure -- \"refuse anything not already shown "
                                  "to work\", not a circuit gain)",
                                  "run_steering.py (REFUSAL_GAP_TILES)")


# ---------------------------------------------------------------------
# mario/entities/ -- the entity model's one flattening assumption
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class EntityParams:
    """NOT the live source -- mario/entities/registry.py keeps defining
    this itself (documented here as the reference, per the same reasoning
    as NetworkParams/HabituationParams above)."""
    entity_width_px: int = _f(16, None,
                                "invented (every enemy-slot entity assumed this wide for the "
                                "looming-angle calculation, real Goomba/Koopa/mushroom hitboxes "
                                "differ in real SMB and this project has never modelled that)",
                                "mario/entities/registry.py (ENTITY_WIDTH_PX)")


# ---------------------------------------------------------------------
# fly/sensing/retinotopy.py -- DORMANT (sprints 023-024, closed negative
# result; retinotopic=False reproduces pre-023 behaviour exactly and is
# the only mode any golden run exercises by default)
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class RetinotopyParams:
    """NOT live in any default run -- retinotopic=False everywhere goldens
    exercise it. Documented for completeness per this phase's own
    instruction not to under-count. NOT the live source, same reasoning as
    NetworkParams above."""
    azimuth_d_ref: float = _f(128.0, None,
                                "invented (retinotopy.py's own docstring: \"the one invented "
                                "numeric scaffold, stated plainly\" -- half the NES screen width, "
                                "used only as an arbitrary but stated saturation point; no "
                                "principled reference distance exists in hex coordinates)",
                                "fly/sensing/retinotopy.py (AZIMUTH_D_REF)")
    hex1_spread_fallback: float = _f(3.0, None,
                                       "invented (fallback bandwidth for a cell with no measured "
                                       "hex-carrying input -- verified empty case in practice; "
                                       "NOT named as a module constant in the live code, only a "
                                       "literal inside receptive_field_centers(), found while "
                                       "building this file, not previously flagged anywhere)",
                                       "fly/sensing/retinotopy.py (receptive_field_centers, literal)")
    hex1_spread_floor: float = _f(0.5, None,
                                    "invented (floor on a single-partner cell's measured spread, "
                                    "which would otherwise be exactly zero and make its tuning "
                                    "curve a delta function; same as above, a bare literal, not a "
                                    "named constant, found while building this file)",
                                    "fly/sensing/retinotopy.py (receptive_field_centers, literal)")


# ---------------------------------------------------------------------
# Test/demo-only -- never active in any default (golden-tested) run
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class DemoParams:
    """mushroom_offset only matters when a caller explicitly passes
    inject_frame= (opt-in only since sprint 011); no golden run does."""
    mushroom_offset: int = _f(-40, None,
                                "invented (spawn position for the synthetic mushroom-injection "
                                "demo, behind Mario so it competes with HOME_BIAS's rightward pull)",
                                "run_steering.py (MUSHROOM_OFFSET)")


ALL_PARAM_CLASSES = (
    NetworkParams, NoiseParams, JumpParams, Dnp02Params, TakeoffParams, SpeedParams,
    SteeringParams, MdnParams, MushroomBodyParams, HabituationParams, OdourParams,
    TerrainParams, EntityParams, RetinotopyParams, DemoParams,
)


def scalar_count() -> int:
    """The honest count this phase exists to produce -- every field on
    every dataclass above, summed directly rather than recalled from
    memory. See docs/SCALARS.md for the full table this generates."""
    return sum(len(fields(cls)) for cls in ALL_PARAM_CLASSES)
