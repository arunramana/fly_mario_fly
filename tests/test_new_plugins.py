"""The newer creatures (buzzy beetle, red koopa, hammer bro, podoboo) and the coin: declared, found in RAM, read in their own levels,
and silent where they must be (World 1-1 is unchanged)."""
import os

import pytest

from fly_mario_fly import registry
from fly_mario_fly.contracts import Scene
from fly_mario_fly.mario import ram as R
from fly_mario_fly.mario import walker
from fly_mario_fly.mario.env import MarioEnv
from fly_mario_fly.mario.facts import load_facts
from fly_mario_fly.rules import validate as V
from fly_mario_fly.rules.lookup import declaration_of
from fly_mario_fly.runner import levels

OBJECTS = registry.list_plugins("objects")
FACTS = load_facts("1-1")
# name -> (type byte, box w, h, level it was read in, x of its first spawn there)
CREATURES = {"buzzy_beetle": (0x02, 16, 16, "6-2", 864), "red_koopa": (0x03, 16, 24, "3-3", 832),
             "hammer_bro": (0x05, 16, 24, "3-1", 1808), "podoboo": (0x0C, 16, 16, "2-4", 256)}


# ---- declared and registered -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", CREATURES)
def test_a_creature_is_declared_as_an_orange_character_and_complies(name):
    d = declaration_of("objects", name)
    assert (d.kind, d.origin) == ("character", "invented") and "RAM" in d.what
    plugin = OBJECTS[name]
    assert plugin.kind == "enemy" and plugin.default_loom_shape == "own_box"
    assert V.check_declaration("character", name, plugin, d, V.make_context()) == []


def test_the_coin_is_a_declared_orange_pickup_that_is_neither_wall_nor_ceiling():
    d = declaration_of("objects", "coin")
    assert (d.kind, d.origin) == ("object", "invented") and OBJECTS["coin"].kind == "pickup"
    assert OBJECTS["coin"].kind not in ("terrain",)                     # headroom and the wall shapes only look at terrain


def test_the_whole_repository_still_complies():
    assert V.validate_all() == []


def test_facts_agree_with_the_plugins_and_no_type_byte_is_shared():
    seen = {}
    for name, p in OBJECTS.items():
        if p.kind == "enemy":
            for b in FACTS["objects"][name]["types"]:
                assert b not in seen, f"type byte {b:#x} is used by both {seen[b]} and {name}"
                seen[b] = name
    for name, (byte, w, h, _, _) in CREATURES.items():
        assert FACTS["objects"][name]["types"] == [byte] and FACTS["objects"][name]["size"] == [w, h]
    assert not set(seen) & set(FACTS["objects"]["non_enemy"]["types"])
    assert FACTS["tiles"]["coin"] == [194, 195] and set(FACTS["tiles"]["coin"]) <= set(FACTS["collision"]["not_solid"])


# ---- found in RAM (poked, so no level is needed) ------------------------------------------------------------------------------

@pytest.mark.parametrize("name", CREATURES)
def test_a_creature_is_found_by_its_type_byte_and_removed_with_it(name):
    byte, w, h, _, _ = CREATURES[name]
    env = MarioEnv()
    try:
        env.reset("1-1", noop=3)
        r = env.facts["ram"]
        for addr, v in ((r["enemy_active"] + 2, 1), (r["enemy_type"] + 2, byte), (r["enemy_state"] + 2, 0),
                        (r["enemy_page"] + 2, 0), (r["enemy_x"] + 2, 200), (r["enemy_y"] + 2, 184)):
            env.poke(addr, v)
        found = OBJECTS[name].find(env.ram, env.facts)
        assert [(o.type, o.id, o.box.x, o.box.w, o.box.h, o.side) for o in found] == [(name, 2, 200, w, h, "ahead")]
        assert all(o.type == name for o in found) and sum(len(p.find(env.ram, env.facts)) for p in OBJECTS.values()
                                                          if p.kind == "enemy") == 1          # and only this plug-in claims it
        env.poke(r["enemy_state"] + 2, 0x22)                              # defeated
        assert OBJECTS[name].find(env.ram, env.facts) == []
        env.poke(r["enemy_state"] + 2, 0)
        OBJECTS[name].remove(env)
        assert OBJECTS[name].find(env.ram, env.facts) == []
    finally:
        env.close()


def test_the_coin_is_found_by_its_tile_ids():
    env = MarioEnv()
    try:
        env.reset("1-1", noop=3)
        facts, g = env.facts, env.facts["grid"]
        wx = R.visible_columns(env.ram, facts)[6]
        for row, tid in ((3, 194), (4, 195)):
            env.poke(facts["ram"]["tile_buffer"] + g["page_bytes"] * ((wx // 256) % 2) + 16 * row + (wx % 256) // g["tile"], tid)
        found = OBJECTS["coin"].find(env.ram, facts)
        assert sorted((o.type, o.box.x, o.box.y, o.box.w, o.box.h, o.state["tile"]) for o in found) == [
            ("coin", wx, 48, 16, 16, 194), ("coin", wx, 64, 16, 16, 195)]
        assert [o.type for p in OBJECTS.values() if p.kind == "terrain" for o in p.find(env.ram, facts)
                if (o.box.x, o.box.y) in ((wx, 48), (wx, 64))] == []          # no terrain plug-in also claims a coin
    finally:
        env.close()


# ---- read in the levels they come from ----------------------------------------------------------------------------------------

def _first_seen(name, level, x, frames=600):
    byte = CREATURES[name][0]
    env = MarioEnv()
    try:
        env.reset(level, noop=3)
        f = env.facts
        walker.walk_to(env, max(40, x - 260))
        w = walker.Walker()
        for _ in range(frames):
            R.sweep_enemies(env, f, keep_types=(byte,))
            if env.step(w.act(env)).done:
                return None
            found = OBJECTS[name].find(env.ram, f)
            if found:
                return found, env.ram[f["ram"]["enemy_state"] + found[0].id]
    finally:
        env.close()


@pytest.mark.parametrize("name", CREATURES)
def test_a_creature_appears_in_the_level_it_was_read_in(name):
    byte, w, h, level, x = CREATURES[name]
    got = _first_seen(name, level, x)
    assert got is not None, f"{name} never showed up in {level}"
    found, state = got
    assert all(o.type == name and o.state["type_byte"] == byte and (o.box.w, o.box.h) == (w, h) for o in found)
    assert int(state) in FACTS["objects"][name]["live_states"]
    assert found[0].box.x >= x - 64


def test_coins_appear_in_4_3_as_a_row_of_boxes():
    env = MarioEnv()
    try:
        env.reset("4-3", noop=2)
        walker.walk_to(env, 320 - 120)
        found = OBJECTS["coin"].find(env.ram, env.facts)
        assert len(found) >= 2 and {o.box.y for o in found} == {32} and {(o.box.w, o.box.h) for o in found} == {(16, 16)}
    finally:
        env.close()


# ---- the level catalogue knows them; World 1-1 does not (its results must not change) ----------------------------------------------

def test_the_level_catalogue_lists_them_where_the_rom_says_they_are():
    for name, (_, _, _, level, _) in CREATURES.items():
        assert name in levels.rom_objects(level), (name, level)
    assert "coin" in levels.rom_objects("4-3")


@pytest.mark.parametrize("name", CREATURES)
def test_no_new_creature_is_in_world_1_1(name):
    assert name not in levels.rom_objects("1-1")


def test_the_coin_is_in_1_1_only_through_its_underground_bonus_room():
    """The ROM's 1-1 stage includes the bonus room under the pipe, which has coins. The overworld, which every fly plays, has none
    (the walk below), and a fly never presses Down, so it never enters the room."""
    assert "coin" in levels.rom_objects("1-1")
    db = __import__("json").load(open(levels.leveldata.__file__.replace("__init__.py", "../facts/level_db.json")))
    overworld = [a for a in db["areas"].values() if "1-1" in a["used_by"] and a["kind"] == "overground"]
    assert overworld and all(not a["coins"] for a in overworld)


def test_none_of_them_is_found_in_1_1_while_walking_it():
    env = MarioEnv()
    try:
        env.reset("1-1", noop=3)
        w = walker.Walker()
        mine = [OBJECTS[n] for n in (*CREATURES, "coin")]
        for _ in range(2500):
            R.sweep_enemies(env, env.facts)                       # the walker's world: no enemies, so only terrain and pickups
            if env.step(w.act(env)).done:
                break
            assert not any(p.find(env.ram, env.facts) for p in mine)
    finally:
        env.close()


# ---- a fly can be attached to them (config) and sees them (needs the brain) -----------------------------------------------------

def test_a_fly_can_attach_looming_to_the_new_creatures():
    from fly_mario_fly.runner import fly_from_dict, validate
    fly = fly_from_dict({"name": "t", "attachments": {"looming": [*CREATURES, "goomba"]}, "whole_fly": ["home"],
                         "actions": ["walk", "steer", "jump"]})
    validate(fly)
    with pytest.raises(ValueError, match="unknown object"):
        validate(fly_from_dict({"name": "t", "attachments": {"looming": ["no_such_creature"]}}))


@pytest.mark.skipif(not os.environ.get("FLY_MARIO_FLY_DATA"), reason="FLY_MARIO_FLY_DATA not set")
def test_a_fly_with_looming_on_a_new_creature_meets_it_in_its_level():
    from fly_mario_fly.runner import Options, Run, fly_from_dict
    fly = fly_from_dict({"name": "t", "attachments": {"looming": ["buzzy_beetle"]}, "whole_fly": ["home"],
                         "actions": ["walk", "steer", "jump"]})
    run = Run(fly, Scene("6-2", noop=3, start=864 - 300, max_frames=900), Options(moment_every_s=0))
    run.play()
    assert "buzzy_beetle" in run.seen
