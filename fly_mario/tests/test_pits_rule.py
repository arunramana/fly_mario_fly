"""The pit rule: pits are measured from where Mario walks, with the game's own idea of 'solid'.

Synthetic frames are built straight into a RAM image (tile buffer + the few bytes the finder reads); the emulator
checks (a tile id the data calls solid really holds Mario up) use the real game."""
import json
from pathlib import Path

import numpy as np
import pytest

from fly_mario import registry
from fly_mario.contracts import Box, ObjectInstance
from fly_mario.mario import ram as R
from fly_mario.mario.env import MarioEnv
from fly_mario.mario.facts import load_facts

FACTS = load_facts("1-1")
PIT = registry.list_plugins("objects")["pit"]
TOWER = registry.list_plugins("shapes")["far_edge_tower"]
DATA = Path(__file__).parent / "data"
GROUND, STEP, PIPE, BRICK, QBLOCK, USED, CASTLE = 84, 97, 16, 81, 192, 196, 98
LAVA = 0x30                      # any non-solid id: the rule needs no code for a new hazard


def frame(cols, feet=176, airborne=False, origin=0):
    """cols: {column index: {row: tile id}} on screen 0 (columns 0-15), everything else empty."""
    ram = np.zeros(0x800, dtype=np.uint8)
    r = FACTS["ram"]
    ram[r["mario_feet_y"]] = feet
    ram[r["player_state"]] = 1 if airborne else 0
    ram[r["jump_origin_y"]] = origin
    for c, rows in cols.items():
        for row, t in rows.items():
            ram[r["tile_buffer"] + 16 * row + c] = t
    return ram


def floor(c0, c1, tile=GROUND):
    return {c: {11: tile, 12: tile} for c in range(c0, c1)}


def pits_of(ram):
    return PIT.find(ram, FACTS)


# ---- which tiles are solid -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("tile", [84, 97, 81, 16, 17, 18, 19, 20, 21, 192, 193, 196, 98])
def test_the_known_solid_tiles(tile):
    assert R.is_solid(FACTS, tile)


@pytest.mark.parametrize("tile", [0, 194, 195, 0x30, 0xff])
def test_empty_coins_and_unknown_hazards_are_not_solid(tile):
    assert not R.is_solid(FACTS, tile)


def test_every_tile_seen_in_the_32_levels_is_classified_and_the_game_agrees():
    """tests/data/tiles_seen.json is what tools/pit_gallery.py saw in the 32 levels. Each id is classified by the rule; then the
    emulator is asked: lay the id as two floor columns and walk across. Solid ids hold Mario at floor height."""
    seen = json.loads((DATA / "tiles_seen.json").read_text())["tiles"]
    assert len(seen) > 20
    env = MarioEnv()
    wrong = []
    for t in seen:
        verdict = R.is_solid(FACTS, t)
        assert isinstance(verdict, bool)
        env.reset("1-1")
        for _ in range(5):
            env.step(())
        for row in (11, 12):
            for c in (8, 9):
                env.poke(0x500 + 16 * row + c, t)
        lowest = 0
        for _ in range(160):
            st = env.step(("right",))
            lowest = max(lowest, int(env.ram[FACTS["ram"]["mario_feet_y"]]))
            if st.done:
                break
        if (lowest <= 176) != verdict:
            wrong.append((t, verdict, lowest))
    assert not wrong, f"the rule and the game disagree (id, rule says solid, lowest feet y): {wrong}"


# ---- support and pits --------------------------------------------------------------------------------------------------
def test_flat_floor_pit_matches_the_old_finder():
    ram = frame({**floor(0, 6), **floor(8, 16)})
    (p,) = pits_of(ram)
    assert (p.box.x, p.box.y, p.box.w, p.box.h) == (96, 176, 32, 32)
    assert p.state["rims"] == (176, 176) and not p.state["open"]


def test_a_pit_running_off_the_screen_is_open():
    (p,) = pits_of(frame(floor(0, 10)))
    assert p.state["open"] and p.box.x == 160


def test_non_solid_ground_row_tiles_are_a_gap_whatever_they_are():
    ram = frame({**floor(0, 6), **floor(6, 8, LAVA), **floor(8, 16)})
    (p,) = pits_of(ram)
    assert (p.box.x, p.box.w) == (96, 32)


def test_a_lower_floor_is_a_fall_not_a_pit_but_no_floor_at_all_is():
    lower = {**floor(0, 6), **{c: {12: GROUND} for c in range(6, 16)}}                  # floor 16 px lower
    assert pits_of(frame(lower)) == []
    deep = {**{c: {7: GROUND, 8: GROUND, 9: GROUND, 10: GROUND, 11: GROUND, 12: GROUND} for c in range(0, 6)}, **floor(6, 16)}
    assert pits_of(frame(deep, feet=112)) == []                                         # standing on a platform, floor far below
    assert len(pits_of(frame({**floor(0, 6), **{c: {} for c in range(6, 16)}}))) == 1


def test_far_rim_is_the_real_top_of_the_stack_where_support_returns():
    ram2 = frame({**floor(0, 6), **{c: {11: GROUND, 12: GROUND, 10: STEP, 9: STEP} for c in range(8, 16)}})   # stairs 2 tiles high
    (p,) = pits_of(ram2)
    assert (p.box.x, p.box.w) == (96, 32)
    assert p.state["rims"] == (176, 144)                                                # far rim 32 px above the near one


def test_pit_measured_from_a_raised_take_off_ground():
    """Mario on a platform (feet 112) with nothing at all beyond its end: a pit measured from 112, not from the screen bottom
    (a column holding only a lower floor does not make one)."""
    platform = {c: {7: GROUND, 8: GROUND, 9: GROUND, 10: GROUND, 11: GROUND, 12: GROUND} for c in range(0, 6)}
    ram = frame({**platform, **floor(10, 16)}, feet=112)
    ram[FACTS["ram"]["tile_buffer"] + 16 * 11 + 10] = 0
    (p,) = pits_of(frame({**platform, **{c: {} for c in range(6, 10)}, **{c: {7: GROUND} for c in range(10, 16)}}, feet=112))
    assert p.box.x == 96 and p.state["ground"] == 112 and p.box.y == 176 and p.state["rims"] == (112, 112)
    bridge = {c: {7: CASTLE} for c in range(6, 16)}
    assert pits_of(frame({**platform, **bridge}, feet=112)) == []


def test_take_off_ground_while_airborne_is_where_the_jump_began():
    assert R.takeoff_ground(frame({}, feet=150, airborne=True, origin=176), FACTS) == 176
    assert R.takeoff_ground(frame({}, feet=150, airborne=True, origin=0), FACTS) == FACTS["grid"]["ground_row"] * 16


def test_flags_too_wide_and_lift_near():
    ram = frame(floor(0, 3))
    (p,) = pits_of(ram)
    assert p.state["too_wide"] and not p.state["lift_near"]
    ram = frame({**floor(0, 6), **floor(8, 16)})
    assert not pits_of(ram)[0].state["too_wide"]
    r = FACTS["ram"]
    ram[r["enemy_active"]] = 1
    ram[r["enemy_type"]] = FACTS["objects"]["lift"]["types"][0]
    ram[r["enemy_x"]] = 130
    assert pits_of(ram)[0].state["lift_near"]


# ---- the tower ---------------------------------------------------------------------------------------------------------
def _tower(box, rims):
    return TOWER.shape(ObjectInstance("pit", 1, box, "ahead", {"loom_rims": rims}), FACTS, {})


def test_tower_stands_on_the_far_rim_top_and_is_as_tall_as_the_gap_or_a_jump():
    flat = _tower(Box(160, 176, 32, 32), (176, 176))
    assert (flat.x, flat.h, flat.y + flat.h) == (192, 32, 176)
    up = _tower(Box(160, 176, 32, 32), (176, 144))                      # far rim 32 px higher: still 32 tall, on 144
    assert (up.h, up.y + up.h) == (32, 144)
    down = _tower(Box(160, 176, 32, 32), (144, 176))                    # far rim lower: no rise, base on the far rim (176)
    assert (down.h, down.y + down.h) == (32, 176)
    wide = _tower(Box(160, 176, 160, 32), (176, 176))
    assert wide.h == FACTS["mario"]["jump_apex"]                        # capped at one jump
