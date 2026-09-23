"""REFACTOR_PLAN.md phase 4: every config/params.py default must equal
the value actually used by the live code, whether that live constant is
now SOURCED from the dataclass (run_mario.py, run_steering.py,
bridge/perception.py -- rewired this phase) or still independently defined
and merely DOCUMENTED by the dataclass (fly/network/dynamics.py,
fly/state/reflex_habituation.py, mario/entities/registry.py,
fly/sensing/retinotopy.py -- deliberately not rewired, see
docs/RUNS.md's phase 4 note for why). Either way, a value drifting out of
sync with its documented home is exactly the kind of thing this test
exists to catch -- it is not a test of behaviour, since goldens already
cover that; it is a test that the documentation is still true.
"""
from __future__ import annotations

import run_mario
import run_steering
import bridge.perception as perception
import fly.network.dynamics as dynamics
import fly.sensing.retinotopy as retinotopy
import fly.state.reflex_habituation as reflex_habituation
import mario.entities.registry as registry
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


def test_demo_params_match_run_steering():
    assert DemoParams().mushroom_offset == run_steering.MUSHROOM_OFFSET


def test_entity_params_match_registry_py():
    assert EntityParams().entity_width_px == registry.ENTITY_WIDTH_PX


def test_retinotopy_params_match_retinotopy_py():
    p = RetinotopyParams()
    assert p.azimuth_d_ref == retinotopy.AZIMUTH_D_REF
