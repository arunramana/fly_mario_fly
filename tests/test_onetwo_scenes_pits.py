"""Lane onetwo: No enemies keeps lifts and moving platforms; the pit is an inverted L at the take-off level; the Fly tab is grouped by kind."""
from pathlib import Path

import numpy as np
import pytest

from fly_mario_fly import registry
from fly_mario_fly.contracts import Box, ObjectInstance
from fly_mario_fly.mario.facts import load_facts
from fly_mario_fly.senses.kit.world import hole_box

FACTS = load_facts("1-2")
R_ = FACTS["ram"]


class FakeEnv:
    def __init__(self, types):
        self.facts = FACTS
        self.ram = np.zeros(0x800, dtype=np.uint8)
        for s, t in enumerate(types):
            self.ram[R_["enemy_active"] + s] = 1
            self.ram[R_["enemy_type"] + s] = t

    def poke(self, addr, v):
        self.ram[addr] = v

    def active(self):
        return [int(self.ram[R_["enemy_type"] + s]) for s in range(5) if self.ram[R_["enemy_active"] + s]]


LIFTS = [0x24, 0x28, 0x2A, 0x2C]


@pytest.mark.parametrize("scene,params", [("no_enemies", {}), ("keep_only", {"types": []})])
def test_scenes_remove_enemies_but_keep_lifts_and_platforms(scene, params):
    env = FakeEnv([0x06, 0x03, LIFTS[0], 0x0D, LIFTS[3]])           # goomba, red koopa, lift, piranha, small lift
    mod = registry.list_plugins("scenes")[scene]
    mod.on_frame(env, params)
    assert env.active() == [LIFTS[0], LIFTS[3]]


def test_every_platform_id_of_the_level_database_is_declared_not_an_enemy():
    ids = set(FACTS["objects"]["non_enemy"]["types"])
    assert ids == set(range(0x24, 0x2D))
    enemy_ids = {b for n, p in registry.list_plugins("objects").items() if p.kind == "enemy" for b in FACTS["objects"][n]["types"]}
    assert not ids & enemy_ids


# ---- the pit as an inverted L ---------------------------------------------------------------------------------------
TOWER = registry.list_plugins("shapes")["far_edge_tower"]


def _tower(rims, w=32, **knobs):
    return TOWER.shape(ObjectInstance("pit", 1, Box(160, 176, w, 32), "ahead", {"loom_rims": rims}), FACTS, knobs)


def test_the_bar_is_one_tile_row_at_the_take_off_level_across_the_gap():
    assert hole_box(Box(160, 176, 32, 32), 112, FACTS) == (160, 112, 32, 16)


@pytest.mark.parametrize("near,far", [(176, 176), (176, 144), (112, 176), (112, 96), (112, 112), (176, 100)])
def test_the_tower_top_is_always_above_the_far_rim(near, far):
    t = _tower((near, far))
    assert t.y + t.h == near                  # it stands on the bar
    assert t.y < far                          # and rises above the far rim
    assert t.h == min(32, FACTS["mario"]["jump_apex"]) + max(0, near - far)


def test_a_wide_pit_is_capped_at_one_jump_plus_the_rise():
    t = _tower((176, 160), w=300)
    assert t.h == FACTS["mario"]["jump_apex"] + 16


# ---- the Fly tab ----------------------------------------------------------------------------------------------------
def test_fly_tab_groups_every_registered_kind_into_three_sub_tabs():
    src = (Path(__file__).resolve().parents[1] / "web" / "src" / "components" / "senseUtil.ts").read_text(encoding="utf-8")
    assert "Enemies" in src and "Objects" in src and "Power-ups" in src
    kinds = {p.kind for p in registry.list_plugins("objects").values()}
    for k in kinds:
        assert f"'{k}'" in src, f"kind {k} has no sub-tab"
