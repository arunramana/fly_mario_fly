"""bridge/controller_modules.py: module list built from config; perception
modules feed stimuli and never act."""
from __future__ import annotations

import dataclasses

import numpy as np

from bridge.controller_modules import (
    GapAheadPerceptionModule, PagePerceptionModule, PerceptionContext, Stimulus, build_modules)
from config.params import GapAheadParams, PagePerceptionParams
from config.project_config import ProjectConfig, from_json
from mario.ram import tile_ram
from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_X,
                                 ADDR_MARIO_PAGE, ADDR_MARIO_X)


def _cfg(**modules):
    return dataclasses.replace(ProjectConfig(), modules=dataclasses.replace(ProjectConfig().modules, **modules))


def test_modules_come_from_config_not_flags():
    assert build_modules(ProjectConfig()) == []
    built = build_modules(_cfg(page_perception=PagePerceptionParams(), gap_ahead=GapAheadParams()))
    assert [m.name for m in built] == ["page_perception", "gap_ahead"]
    assert all(m.kind == "perception" for m in built)


def test_config_roundtrip_keeps_an_enabled_module():
    cfg = _cfg(gap_ahead=GapAheadParams(perceive_tiles=3))
    assert from_json(cfg.to_json()).modules.gap_ahead.perceive_tiles == 3
    assert from_json(_cfg(page_perception=PagePerceptionParams()).to_json()).modules.page_perception is not None


def test_perception_modules_only_set_stimuli():
    stim = Stimulus()
    PagePerceptionModule(PagePerceptionParams()).perceive(
        PerceptionContext(ram=None, mario_x=0, gap_w=0, distance_to_edge=None, config=ProjectConfig()), stim)
    assert stim.page_aware_looming and stim.gap_input is None
    assert set(dataclasses.asdict(stim)) == {"page_aware_looming", "gap_input", "mb_extra"}  # stimuli only, no action fields


def _ground_ram(gap_cols, mario_x=0):
    ram = np.zeros(tile_ram.BUF_END, dtype=np.uint8)
    ram[tile_ram.ADDR_MARIO_X] = mario_x
    for col in range(0, 12):
        if col not in gap_cols:
            ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * 16 + col] = tile_ram.GROUND_ID
    return ram


def test_gap_ahead_grows_toward_the_edge_and_matches_gap_width_there():
    m = GapAheadPerceptionModule(GapAheadParams(perceive_tiles=4))
    cfg = ProjectConfig()
    vals = []
    for mario_col in (0, 1, 2):                      # pit = cols 4-6 (3 wide)
        ram = _ground_ram({4, 5, 6}, mario_x=mario_col * 16)
        stim = Stimulus()
        d = tile_ram.distance_to_gap(ram, 8)
        m.perceive(PerceptionContext(ram=ram, mario_x=0, gap_w=0, distance_to_edge=d, config=cfg), stim)
        vals.append(stim.gap_input)
    assert vals[0] < vals[1] < vals[2]
    ram = _ground_ram({4, 5, 6}, mario_x=3 * 16)      # at the edge: same as today's gap_width
    assert tile_ram.gap_width(ram, 8) == 3
    stim = Stimulus()
    m.perceive(PerceptionContext(ram=ram, mario_x=0, gap_w=3, distance_to_edge=1, config=cfg), stim)
    assert stim.gap_input == 3


def test_page_aware_distance_sees_an_enemy_across_a_page_boundary():
    from bridge.perception import enemy_thetas
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_PAGE], ram[ADDR_MARIO_X] = 6, 242
    ram[ADDR_ENEMY_ACTIVE], ram[ADDR_ENEMY_PAGE], ram[ADDR_ENEMY_X] = 1, 7, 1
    prev = {"L": 0.0, "R": 0.0}
    _, _, d_plain = enemy_thetas(ram, 242, prev)
    _, _, d_page = enemy_thetas(ram, 242, prev, page_aware=True)
    assert d_plain["R"] is None and d_plain["L"] < -200      # read as far BEHIND
    assert d_page["R"] == 15                                 # actually 15px ahead
