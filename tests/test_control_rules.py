# What this file does, in plain English:
# Checks the on/off switch for each hand-coded control rule listed in
# docs/CONTROL_AUDIT.md. With a switch on (the default) the rule acts as it
# always has; with it off the rule is gone and the circuit alone decides.
"""ControlRules (config/params.py): each switch removes exactly its rule from
FullPolicy.act. Synthetic RAM, no emulator. tests/test_golden.py is the proof
that the all-on default is byte-identical to before."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from bridge.full_policy import FullPolicy
from config.params import CONTROL_RULE_LABELS, ControlRules
from config.project_config import ProjectConfig, from_json
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE, ADDR_MARIO_X, POWERUP_ID)

GOOMBA = 0x06
MARIO_COL = 3


def _ram(pit_cols=(), wall_cols=(), wall_height=3, goomba_dx=None, mushroom_dx=None):
    ram = np.zeros(0x800, dtype=np.uint8)
    ram[ADDR_MARIO_PAGE] = 0
    ram[ADDR_MARIO_X] = MARIO_COL * 16
    for col in range(16):
        if col not in pit_cols:
            ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * 16 + col] = tile_ram.GROUND_ID
    for col in wall_cols:
        for row in range(tile_ram.GROUND_ROW - wall_height, tile_ram.GROUND_ROW):
            ram[tile_ram.BUF1_ADDR + row * 16 + col] = 0x10
    for slot, (dx, kind) in enumerate(((goomba_dx, GOOMBA), (mushroom_dx, POWERUP_ID))):
        if dx is not None:
            ram[ADDR_ENEMY_ACTIVE + slot] = 1
            ram[ADDR_ENEMY_TYPE + slot] = kind
            ram[ADDR_ENEMY_X + slot] = MARIO_COL * 16 + dx
    return ram


def _policy(**rules):
    cfg = dataclasses.replace(ProjectConfig(), rules=ControlRules(**rules))
    return FullPolicy(cfg)


def _run(policy, ram, frames):
    infos = []
    for _ in range(frames):
        policy.act(SimpleNamespace(ram=ram))
        infos.append(dict(policy.last_info))
    return infos


def test_every_rule_has_a_switch_default_on_and_a_label():
    assert all(getattr(ControlRules(), f.name) is True for f in dataclasses.fields(ControlRules))
    assert set(CONTROL_RULE_LABELS) == {f.name for f in dataclasses.fields(ControlRules)}


def test_switches_roundtrip_and_old_configs_default_to_on():
    cfg = dataclasses.replace(ProjectConfig(), rules=ControlRules(refusal=False, jump_hold=False))
    back = from_json(cfg.to_json())
    assert back.rules.refusal is False and back.rules.jump_hold is False and back.rules.jump_cooldown is True
    d = cfg.to_dict()
    del d["rules"]
    from config.project_config import from_dict
    assert from_dict(d).rules == ControlRules()


# ---- row 10: refusal -------------------------------------------------------

def test_refusal_switch():
    ram = _ram(pit_cols=range(MARIO_COL + 1, MARIO_COL + 8))   # a 7-tile pit right ahead
    assert _run(_policy(), ram, 1)[-1]["refusing"] is True
    assert _run(_policy(refusal=False), ram, 1)[-1]["refusing"] is False


# ---- rows 6-8: climb stall, reflex, habituation ---------------------------

def _blocked():
    return _ram(wall_cols=(MARIO_COL + 1,), wall_height=2)


def test_climb_reflex_fires_only_with_stall_and_reflex_on():
    p = _policy()
    _run(p, _blocked(), 40)
    assert p.n_climb_hops >= 1
    for rule in ("climb_stall", "climb_reflex"):
        p = _policy(**{rule: False})
        _run(p, _blocked(), 40)
        assert p.n_climb_hops == 0 and p.n_climb_jumps == 0, rule


def test_climb_habituation_switch_stops_the_give_up():
    p = _policy()
    _run(p, _blocked(), 600)
    assert p.hab_climb.hab_level > 0
    p = _policy(climb_habituation=False)
    _run(p, _blocked(), 600)
    assert p.hab_climb.hab_level == 0 and p.n_climb_hops + p.n_climb_jumps > 3


# ---- row 11: walk suppression ---------------------------------------------

def test_walk_suppression_switch_keeps_the_walk_drive_while_stalled():
    on = _run(_policy(climb_reflex=False), _blocked(), 30)[-1]["dnp09_val"]
    off = _run(_policy(climb_reflex=False, walk_suppression=False), _blocked(), 30)[-1]["dnp09_val"]
    assert off > on


# ---- row 12: odour brake ---------------------------------------------------

def test_odour_brake_switch_keeps_the_walk_drive_near_food():
    ram = _ram(mushroom_dx=20)
    # climb_stall off in both: a motionless synthetic Mario would otherwise read as "busy"
    on = _run(_policy(climb_stall=False), ram, 30)[-1]["dnp09_val"]
    off = _run(_policy(climb_stall=False, odour_brake=False), ram, 30)[-1]["dnp09_val"]
    assert off > on


# ---- rows 1-3: jump hold, cooldown, long-jump selection -------------------

def _goomba_ram():
    return _ram(goomba_dx=12)


def test_jump_hold_switch():
    p = _policy()
    infos = _run(p, _goomba_ram(), 60)
    assert p.n_escape_jumps >= 1 and any(i["press_a"] for i in infos)
    p = _policy(jump_hold=False)
    infos = _run(p, _goomba_ram(), 60)
    assert p.n_escape_jumps >= 1 and not any(i["press_a"] for i in infos)   # commits, but no counter drives A


def test_jump_cooldown_switch():
    p = _policy()
    _run(p, _goomba_ram(), 40)
    assert p.jump_cooldown > 0 or p.n_escape_jumps == 0 or p.jump_hold > 0
    p = _policy(jump_cooldown=False)
    infos = _run(p, _goomba_ram(), 200)
    assert p.jump_cooldown == 0
    q = _policy()
    _run(q, _goomba_ram(), 200)
    assert p.n_escape_jumps > q.n_escape_jumps            # no cooldown -> more commits in the same time


def test_long_jump_selection_switch():
    ram = _ram(goomba_dx=12, pit_cols=(MARIO_COL + 1, MARIO_COL + 2))
    p = _policy()
    assert any(i["long_jump"] for i in _run(p, ram, 120)), "default must still pick a long jump here"
    p = _policy(long_jump_select=False)
    assert not any(i["long_jump"] for i in _run(p, ram, 120))


# ---- rows 4-5: escape habituation, MDN backup -----------------------------

def test_escape_habituation_and_mdn_backup_switches():
    ram = _goomba_ram()
    p = _policy()
    infos = _run(p, ram, 700)
    assert any(i["hab_escape_level"] > 0 for i in infos)
    assert any(i["mdn_backing_up"] for i in infos), "habituation hands over to MDN"
    p = _policy(mdn_backup=False)
    infos = _run(p, ram, 700)
    assert not any(i["mdn_backing_up"] for i in infos)
    p = _policy(escape_habituation=False)
    infos = _run(p, ram, 700)
    assert all(i["hab_escape_level"] == 0 for i in infos)
    assert not any(i["mdn_backing_up"] for i in infos)


@pytest.mark.parametrize("rule", [f.name for f in dataclasses.fields(ControlRules)])
def test_each_switch_alone_leaves_a_runnable_policy(rule):
    p = _policy(**{rule: False})
    _run(p, _goomba_ram(), 5)
