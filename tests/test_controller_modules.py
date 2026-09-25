"""bridge/controller_modules.py: module list built from config; the
grounded pit module fires only on the ground with a fresh A press."""
from __future__ import annotations

import dataclasses

from bridge.controller_modules import ActContext, GroundedPitModule, Proposal, build_modules
from config.params import GroundedPitParams
from config.project_config import ProjectConfig


def _ctx(dist, state=0, prev_a=False):
    return ActContext(ram=None, mario_x=0, gap_w=0, distance_to_edge=dist, dlmn_val=0.0, enemy_d_px=None,
                      player_state=state, prev_press_a=prev_a, jump_hold=0, jump_cooldown=9,
                      config=ProjectConfig())


def test_modules_come_from_config_not_flags():
    assert build_modules(ProjectConfig()) == []
    cfg = dataclasses.replace(ProjectConfig(), modules=dataclasses.replace(
        ProjectConfig().modules, grounded_pit=GroundedPitParams()))
    assert [m.name for m in build_modules(cfg)] == ["grounded_pit"]


def test_grounded_pit_fires_only_on_the_ground_with_a_fresh_press():
    m = GroundedPitModule(GroundedPitParams())
    for ctx, fires in ((_ctx(2), True), (_ctx(2, state=1), False), (_ctx(2, prev_a=True), False),
                       (_ctx(3), False), (_ctx(None), False)):
        out = Proposal()
        m.propose(ctx, out)
        assert out.force_long_jump is fires


def test_run_up_holds_b_even_when_not_yet_firing():
    m = GroundedPitModule(GroundedPitParams())
    out = Proposal()
    m.propose(_ctx(4), out)
    assert out.force_press_b and not out.force_long_jump


def test_config_roundtrip_keeps_an_enabled_module():
    from config.project_config import from_json
    cfg = dataclasses.replace(ProjectConfig(), modules=dataclasses.replace(
        ProjectConfig().modules, grounded_pit=GroundedPitParams(trigger_distance_tiles=3)))
    assert from_json(cfg.to_json()).modules.grounded_pit.trigger_distance_tiles == 3


def test_threat_bypass_lifts_only_the_cooldown_near_a_grounded_threat():
    from bridge.controller_modules import ThreatCooldownBypassModule
    from config.params import ThreatBypassParams
    m = ThreatCooldownBypassModule(ThreatBypassParams(distance_px=40))
    for d, state, prev_a, expect in ((20, 0, False, True), (60, 0, False, False), (20, 1, False, False),
                                     (20, 0, True, False), (None, 0, False, False), (-5, 0, False, False)):
        ctx = _ctx(None, state=state, prev_a=prev_a)
        ctx.enemy_d_px = d
        out = Proposal()
        m.propose(ctx, out)
        assert out.bypass_cooldown is expect
        assert not (out.force_dnp01 or out.force_long_jump or out.force_press_b)


def test_page_threat_sees_an_enemy_across_a_page_boundary():
    import numpy as np
    from bridge.controller_modules import PageAwareThreatModule
    from config.params import PageAwareThreatParams
    from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_X,
                                     ADDR_MARIO_PAGE, ADDR_MARIO_X)
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_PAGE], ram[ADDR_MARIO_X] = 6, 242          # abs 1778
    ram[ADDR_ENEMY_ACTIVE], ram[ADDR_ENEMY_PAGE], ram[ADDR_ENEMY_X] = 1, 7, 1   # abs 1793: 15px ahead
    ctx = _ctx(None)
    ctx.ram = ram
    m = PageAwareThreatModule(PageAwareThreatParams(trigger_px=40))
    out = Proposal()
    m.propose(ctx, out)
    assert out.force_dnp01 and out.bypass_cooldown
    ram[ADDR_ENEMY_PAGE] = 6   # same page: the byte alone would say 241px behind
    out = Proposal()
    m.propose(ctx, out)
    assert not out.force_dnp01
