# What this file does, in plain English:
# Checks the "? block ahead" perception module: the tile map gives how far
# ahead and how high the nearest unhit "?" block is, and the module turns that
# into inputs to the fly's learning centre (and, if asked, a faint looming
# cue). It never presses a button, and with the module off nothing changes.
"""tile_ram.question_blocks_ahead + QBlockAheadPerceptionModule (docs/SPEC_learning_v2.md
section 5, invariant 8): stimuli only."""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

import numpy as np

from bridge.controller_modules import PerceptionContext, QBlockAheadPerceptionModule, Stimulus, build_modules
from bridge.entity_profiles import KindProfile
from bridge.full_policy import FullPolicy
from config.params import MbSpatialInputParams, ModulesConfig, QBlockAheadParams
from config.project_config import ProjectConfig
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_MARIO_X


def _ram(blocks=(), mario_x=0):
    """Flat ground; `blocks` = [(column, row, tile id)]."""
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_X] = mario_x
    for col in range(16):
        ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * 16 + col] = tile_ram.GROUND_ID
    for col, row, tile in blocks:
        ram[tile_ram.BUF1_ADDR + row * 16 + col] = tile
    return ram


def test_question_blocks_ahead_reports_distance_and_height_nearest_first():
    Q = tile_ram.QUESTION_COIN_ID
    assert tile_ram.question_blocks_ahead(_ram()) == []
    ram = _ram([(5, 7, Q), (2, 5, tile_ram.QUESTION_POWERUP_ID)])
    assert tile_ram.question_blocks_ahead(ram) == [(2, 6), (5, 4)]     # (tiles ahead, tiles above the ground)
    assert tile_ram.question_blocks_ahead(ram, max_tiles=3) == [(2, 6)]  # out of range is not perceived
    assert tile_ram.question_blocks_ahead(_ram([(0, 7, Q)])) == [(0, 4)]  # directly overhead
    assert tile_ram.question_blocks_ahead(_ram([(2, 7, Q)], mario_x=64)) == []   # behind Mario
    assert tile_ram.question_blocks_ahead(_ram([(5, 7, tile_ram.USED_BLOCK_ID)])) == []   # already hit


def _perceive(module, ram, profiles=None):
    stim = Stimulus()
    module.perceive(PerceptionContext(ram=ram, mario_x=int(ram[ADDR_MARIO_X]), gap_w=0, distance_to_edge=None,
                                      config=ProjectConfig(), profiles=profiles), stim)
    return stim


def test_module_reports_closeness_and_height_and_no_looming_by_default():
    m = QBlockAheadPerceptionModule(QBlockAheadParams(perceive_tiles=8))
    none = _perceive(m, _ram())
    assert none.mb_extra == (0.0, 0.0) and none.qblock_tiles == -1
    s = _perceive(m, _ram([(2, 7, tile_ram.QUESTION_COIN_ID)]))
    assert s.mb_extra == ((8 - 2) / 8, 4 / tile_ram.GROUND_ROW)
    assert (s.qblock_tiles, s.qblock_height_tiles) == (2, 4)
    assert s.qblock_theta == 0.0 and s.qblock_dtheta == 0.0            # looming_gain 0 = route off
    near = _perceive(m, _ram([(1, 7, tile_ram.QUESTION_COIN_ID)]))
    assert near.mb_extra[0] > s.mb_extra[0]                            # closer = stronger


def test_looming_route_and_profile_weight():
    m = QBlockAheadPerceptionModule(QBlockAheadParams(perceive_tiles=8, looming_gain=2.0))
    ram = _ram([(2, 7, tile_ram.QUESTION_COIN_ID)])
    s = _perceive(m, ram)
    theta = 2 * math.atan(16 / (2 * 32))
    assert math.isclose(s.qblock_theta, 2.0 * theta) and math.isclose(s.qblock_dtheta, 2.0 * theta)
    m2 = QBlockAheadPerceptionModule(QBlockAheadParams(perceive_tiles=8, looming_gain=2.0))
    profiles = SimpleNamespace(get=lambda kind: KindProfile(cue_weight=0.5))
    half = _perceive(m2, ram, profiles)
    assert math.isclose(half.qblock_theta, 0.5 * s.qblock_theta)
    assert math.isclose(half.mb_extra[0], 0.5 * s.mb_extra[0])         # the profile scales both routes
    # It only ever sets stimulus fields -- nothing an action could be read from.
    assert not any("press" in f.name or "jump" in f.name for f in dataclasses.fields(s))


def test_off_by_default_and_kc_inputs_grow_by_its_own_two():
    assert ModulesConfig().qblock_ahead is None
    assert "qblock_ahead" not in [m.name for m in build_modules(ProjectConfig())]
    assert FullPolicy(config=ProjectConfig()).mb_proj.shape[1] == 7
    on = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(qblock_ahead=QBlockAheadParams()))
    assert FullPolicy(config=on).mb_proj.shape[1] == 9
    both = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(
        mb_spatial_inputs=MbSpatialInputParams(), qblock_ahead=QBlockAheadParams()))
    p = FullPolicy(config=both)
    assert p.mb_proj.shape[1] == 11 and p.mb_spatial and p.n_mb_extra == 4


def test_a_run_with_the_module_on_logs_the_cue_and_runs():
    import run_steering
    cfg = dataclasses.replace(ProjectConfig(), modules=ModulesConfig(
        qblock_ahead=QBlockAheadParams(perceive_tiles=8, looming_gain=0.5)))
    tel, info = run_steering.main(out_mp4="IGNORED_qblock.mp4", record_video=False, write_telemetry=False,
                                  level="1-1", max_frames=150, sigma=0.0, seed=0, config=cfg)
    assert {"qblock_tiles", "qblock_height", "qblock_theta"} <= set(tel.columns)
    assert (tel["qblock_tiles"] >= 0).any(), "1-1's first ? block is within 8 tiles of the start"
    plain, _ = run_steering.main(out_mp4="IGNORED_qblock2.mp4", record_video=False, write_telemetry=False,
                                 level="1-1", max_frames=150, sigma=0.0, seed=0)
    assert "qblock_tiles" not in plain.columns                          # off: no new columns
