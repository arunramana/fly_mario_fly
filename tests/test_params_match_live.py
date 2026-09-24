# What this file does, in plain English:
# Checks that every default value in the central settings file
# (config/params.py) equals the value the running code actually uses, in
# run_mario.py, run_steering.py and several fly, bridge and game modules.
# This keeps the settings file an accurate record of what the code does.
"""
Every config/params.py default equals the value the live code uses,
whether the live constant is sourced from the dataclass (run_mario.py,
run_steering.py, bridge/perception.py) or still defined separately and
only documented there (dynamics.py, reflex_habituation.py, registry.py,
retinotopy.py). Checks the documentation is true; the goldens cover
behaviour.
"""
from __future__ import annotations

import inspect

import run_mario
import run_steering
import bridge.perception as perception
import fly.network.dynamics as dynamics
import fly.network.network as network
import fly.sensing.retinotopy as retinotopy
import fly.state.reflex_habituation as reflex_habituation
import mario.entities.registry as registry
from config.project_config import ScenarioParams
from config.params import (
    Dnp02Params, JumpParams, MdnParams, MushroomBodyParams, NetworkParams,
    OdourParams, SpeedParams, SteeringParams, TakeoffParams, TerrainParams,
    HabituationParams, EntityParams, RetinotopyParams, DemoParams,
)


def test_network_params_match_dynamics_py():
    p = NetworkParams()
    assert p.alpha == dynamics.ALPHA
    assert p.clip == dynamics.CLIP
    assert p.substeps == dynamics.SUBSTEPS


def test_jump_params_match_run_mario():
    p = JumpParams()
    assert p.g == run_mario.G
    assert p.dnp01_spike_threshold == run_mario.DNP01_SPIKE_THRESHOLD
    assert p.ttmn_press_threshold == run_mario.TTMN_PRESS_THRESHOLD
    assert p.spike_amp == run_mario.SPIKE_AMP
    assert p.jump_hold_frames == run_mario.JUMP_HOLD_FRAMES
    assert p.jump_cooldown_frames == run_mario.JUMP_COOLDOWN_FRAMES


def test_dnp02_params_match_run_steering():
    p = Dnp02Params()
    assert p.g == run_steering.G_DNP02
    assert p.spike_threshold == run_steering.DNP02_SPIKE_THRESHOLD
    assert p.alpha == run_steering.DNP02_ALPHA


def test_takeoff_params_match_run_steering():
    p = TakeoffParams()
    assert p.g == run_steering.G_TAKEOFF
    assert p.gap_gain == run_steering.GAP_GAIN
    assert p.dlmn_recruit_threshold == run_steering.DLMN_RECRUIT_THRESHOLD
    assert p.long_jump_hold_frames == run_steering.LONG_JUMP_HOLD_FRAMES
    assert p.gap_lookahead_tiles == run_steering.GAP_LOOKAHEAD_TILES


def test_speed_params_match_run_steering():
    p = SpeedParams()
    assert p.g == run_steering.G_SPEED
    assert p.walk_drive == run_steering.WALK_DRIVE
    assert p.walk_suppression == run_steering.WALK_SUPPRESSION
    assert p.dnp09_speed_threshold == run_steering.DNP09_SPEED_THRESHOLD


def test_steering_params_match_run_steering():
    p = SteeringParams()
    assert p.g == run_steering.G_STEER
    assert p.home_bias == run_steering.HOME_BIAS
    assert p.climb_stall_frames == run_steering.CLIMB_STALL_FRAMES
    assert p.climb_hop_small_frames == run_steering.CLIMB_HOP_SMALL_FRAMES
    assert p.climb_hop_big_frames == run_steering.CLIMB_HOP_BIG_FRAMES
    assert p.climb_jump_frames == run_steering.CLIMB_JUMP_FRAMES
    assert p.climb_cooldown_frames == run_steering.CLIMB_COOLDOWN_FRAMES
    assert p.climb_clear_distance == run_steering.CLIMB_CLEAR_DISTANCE


def test_mdn_params_match_run_steering():
    p = MdnParams()
    assert p.g == run_steering.G_MDN
    assert p.mdn_drive == run_steering.MDN_DRIVE
    assert p.mdn_threshold == run_steering.MDN_THRESHOLD
    assert p.mdn_backup_frames == run_steering.MDN_BACKUP_FRAMES


def test_mushroom_body_params_match_run_steering():
    p = MushroomBodyParams()
    assert p.kc_sparsity == run_steering.KC_SPARSITY
    assert p.trace_decay == run_steering.TRACE_DECAY
    assert p.learning_rate == run_steering.LEARNING_RATE


def test_habituation_params_match_reflex_habituation_py():
    p = HabituationParams()
    assert p.hab_progress_px == reflex_habituation.HAB_PROGRESS_PX
    assert p.hab_give_up == reflex_habituation.HAB_GIVE_UP


def test_odour_params_match_live():
    p = OdourParams()
    assert p.odour_gain == run_steering.ODOUR_GAIN
    assert p.hunger_mult_hungry == perception.HUNGER_MULT_HUNGRY
    assert p.hunger_mult_sated == perception.HUNGER_MULT_SATED
    from fly.sensing.olfactory_adaptation import ALPHA_ADAPT
    assert p.alpha_adapt == ALPHA_ADAPT


def test_terrain_params_match_run_steering():
    assert TerrainParams().refusal_gap_tiles == run_steering.REFUSAL_GAP_TILES
    assert TerrainParams().refusal_gap_margin_tiles == run_steering.REFUSAL_GAP_MARGIN_TILES


def test_demo_params_match_run_steering():
    assert DemoParams().mushroom_offset == run_steering.MUSHROOM_OFFSET
    assert DemoParams().wide_gap_lead_tiles == run_steering.WIDE_GAP_LEAD_TILES


def test_scenario_params_match_run_steering_main_default():
    """docs/CODE_AUDIT.md section H: run_steering.MAX_FRAMES and
    ScenarioParams.max_frames used to be two independent `1200` literals
    -- main()'s own default now reads ScenarioParams() directly, so
    there is exactly one home, not two kept equal by hand."""
    default = inspect.signature(run_steering.main).parameters["max_frames"].default
    assert default == ScenarioParams().max_frames


def test_network_params_denormal_threshold_matches_flush_denormals_default():
    """fly/network/network.py's Network.flush_denormals keeps its own
    hardcoded default (like dynamics.ALPHA/CLIP) for callers with no
    config in hand (scripts/denormal_probe.py) -- FullPolicy's own call
    sites pass config.network.denormal_flush_threshold explicitly."""
    default = inspect.signature(network.Network.flush_denormals).parameters["threshold"].default
    assert default == NetworkParams().denormal_flush_threshold


def test_entity_params_match_registry_py():
    assert EntityParams().entity_width_px == registry.ENTITY_WIDTH_PX


def test_retinotopy_params_match_retinotopy_py():
    p = RetinotopyParams()
    assert p.azimuth_d_ref == retinotopy.AZIMUTH_D_REF
