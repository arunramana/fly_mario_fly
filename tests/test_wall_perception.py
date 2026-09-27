# What this file does, in plain English:
# Checks the wall/step perception: the tile map gives distance and height of a
# pipe, stair or block stack ahead, and the wall module turns that into a
# looming stimulus (and/or a takeoff current) for the circuit -- never a button.
"""tile_ram.obstacle_ahead + WallAheadPerceptionModule (CONTROL_AUDIT.md,
invariant 8): stimuli only."""
from __future__ import annotations

import dataclasses
import math
from types import SimpleNamespace

import numpy as np

from bridge.controller_modules import PerceptionContext, Stimulus, WallAheadPerceptionModule, build_modules
from bridge.full_policy import FullPolicy
from config.params import ControlRules, WallAheadParams
from config.project_config import ProjectConfig, from_json
from mario.ram import tile_ram
from mario.ram.addresses import ADDR_MARIO_PAGE, ADDR_MARIO_X


def _ram(wall_col=None, height=2, mario_x=0, floating_row=None):
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_X] = mario_x
    for col in range(16):
        ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * 16 + col] = tile_ram.GROUND_ID
    if wall_col is not None:
        for row in range(tile_ram.GROUND_ROW - height, tile_ram.GROUND_ROW):
            ram[tile_ram.BUF1_ADDR + row * 16 + wall_col] = 0x10
    if floating_row is not None:
        ram[tile_ram.BUF1_ADDR + floating_row * 16 + 2] = 0x51
    return ram


def test_obstacle_ahead_reports_distance_and_height():
    assert tile_ram.obstacle_ahead(_ram()) is None
    assert tile_ram.obstacle_ahead(_ram(wall_col=4, height=2)) == (4, 2)
    assert tile_ram.obstacle_ahead(_ram(wall_col=4, height=4)) == (4, 4)
    assert tile_ram.obstacle_ahead(_ram(wall_col=9, height=2), max_tiles=6) is None      # out of range


def test_a_floating_block_is_not_a_wall_and_a_question_block_never_is():
    assert tile_ram.obstacle_ahead(_ram(floating_row=7)) is None
    ram = _ram()
    ram[tile_ram.BUF1_ADDR + 10 * 16 + 2] = tile_ram.QUESTION_COIN_ID
    assert tile_ram.obstacle_ahead(ram) is None


def _perceive(module, ram, mario_x=0):
    stim = Stimulus()
    module.perceive(PerceptionContext(ram=ram, mario_x=mario_x, gap_w=0, distance_to_edge=None,
                                      config=ProjectConfig()), stim)
    return stim


def test_looming_angle_follows_the_mario_eye_formula_and_grows_on_approach():
    m = WallAheadPerceptionModule(WallAheadParams(perceive_tiles=6, looming_gain=1.0, takeoff_gain=0.0))
    thetas, dthetas = [], []
    for x in (0, 16, 32):                                   # wall in column 4, Mario walks up to it
        stim = _perceive(m, _ram(wall_col=4, height=2, mario_x=x), mario_x=x)
        d = 4 * 16 - x
        assert math.isclose(stim.wall_theta, 2 * math.atan(2 * 16 / (2 * d)))
        thetas.append(stim.wall_theta)
        dthetas.append(stim.wall_dtheta)
    assert thetas[0] < thetas[1] < thetas[2]
    assert dthetas[1] > 0 and dthetas[2] > 0
    assert _perceive(m, _ram(mario_x=32), mario_x=32).wall_dtheta < 0   # wall gone: theta falls back


def test_a_taller_wall_looms_larger():
    m = WallAheadPerceptionModule(WallAheadParams())
    low = _perceive(m, _ram(wall_col=4, height=1)).wall_theta
    m.reset()
    high = _perceive(m, _ram(wall_col=4, height=4)).wall_theta
    assert high > low > 0


def test_each_route_has_its_own_gain():
    ram = _ram(wall_col=4, height=3)
    only_loom = _perceive(WallAheadPerceptionModule(WallAheadParams(looming_gain=1.0, takeoff_gain=0.0)), ram)
    only_takeoff = _perceive(WallAheadPerceptionModule(WallAheadParams(looming_gain=0.0, takeoff_gain=1.0)), ram)
    assert only_loom.wall_theta > 0 and only_loom.wall_takeoff == 0.0
    assert only_takeoff.wall_theta == 0.0 and only_takeoff.wall_dtheta == 0.0 and only_takeoff.wall_takeoff > 0
    assert only_takeoff.wall_takeoff < _perceive(
        WallAheadPerceptionModule(WallAheadParams(looming_gain=0.0, takeoff_gain=1.0)),
        _ram(wall_col=4, height=3, mario_x=48), mario_x=48).wall_takeoff       # ramps up as it nears


def test_module_is_perception_and_off_by_default_and_roundtrips():
    assert build_modules(ProjectConfig()) == []
    cfg = dataclasses.replace(ProjectConfig(), modules=dataclasses.replace(
        ProjectConfig().modules, wall_ahead=WallAheadParams(takeoff_gain=0.5)))
    (m,) = build_modules(cfg)
    assert m.name == "wall_ahead" and m.kind == "perception" and not hasattr(m, "propose")
    assert from_json(cfg.to_json()).modules.wall_ahead.takeoff_gain == 0.5


def test_the_wall_reaches_the_looming_detectors_but_presses_nothing():
    cfg = dataclasses.replace(ProjectConfig(), modules=dataclasses.replace(
        ProjectConfig().modules, wall_ahead=WallAheadParams()),
        rules=ControlRules(climb_stall=False, climb_reflex=False))
    plain = FullPolicy(dataclasses.replace(cfg, modules=dataclasses.replace(cfg.modules, wall_ahead=None)))
    walled = FullPolicy(cfg)
    ram = _ram(wall_col=4, height=4, mario_x=48)
    for _ in range(3):
        plain.act(SimpleNamespace(ram=ram))
        walled.act(SimpleNamespace(ram=ram))
    assert walled.last_info["hj"][walled.j_msk["LC4_R"]].mean() > plain.last_info["hj"][plain.j_msk["LC4_R"]].mean()
    assert walled.last_info["hj"][walled.j_msk["LPLC2_R"]].mean() > plain.last_info["hj"][plain.j_msk["LPLC2_R"]].mean()
    assert walled.last_info["extras"]["wall_tiles"] == 1 and walled.last_info["extras"]["wall_height"] == 4
    assert "wall_tiles" not in plain.last_info["extras"]
