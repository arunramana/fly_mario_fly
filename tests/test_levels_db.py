"""The level database (mario/facts/level_db.json, read from the game ROM by tools/read_rom_levels.py): what it holds, known facts of
the real game, and that the committed file is what the ROM gives. No emulator here (tests/test_levels_emulator.py compares with it)."""
import importlib.util
import json
from pathlib import Path

import pytest

from fly_mario.mario import leveldata
from fly_mario.mario.env import level_ids
from fly_mario.mario.leveldata import areas as A, build, rom as R

STAGES = level_ids()[:32]
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def db():
    return leveldata.load()


def test_all_32_stages_and_the_three_whole_game_envs_are_present(db):
    assert list(db["stages"]) == STAGES
    assert set(db["envs"]) == {"full", "random", "lost_levels"} and db["envs"]["random"]["stages"] == STAGES
    for sid, st in db["stages"].items():
        assert st["main"] in db["areas"] and all(a["key"] in db["areas"] for a in st["areas"])
        assert st["kind"] in {"overground", "underground", "water", "castle", "athletic"} and st["width"] > 1500, sid
        assert st["time_limit"] in (400, 300, 200) and st["end"] and st["end"]["kind"] == ("axe" if st["kind"] == "castle" else "flagpole")
        assert st["summary"]["tile_ids"] and st["summary"]["enemy_ids"] is not None
    assert "mushroom or a fire flower" in db["note_power_up"]            # the file says what "power-up" means


def test_stage_kinds_match_the_game(db):
    kinds = {sid: st["kind"] for sid, st in db["stages"].items()}
    assert [kinds[f"{w}-4"] for w in range(1, 9)] == ["castle"] * 8
    assert kinds["1-2"] == kinds["4-2"] == "underground" and kinds["2-2"] == kinds["7-2"] == "water"
    assert kinds["1-1"] == "overground" and kinds["1-3"] == "athletic"
    assert {sid for sid, k in kinds.items() if k == "athletic"} == {"1-3", "2-3", "3-3", "4-3", "5-3", "6-3", "7-3"}


def test_1_1_known_facts(db):
    st, a = db["stages"]["1-1"], db["areas"]["ground6"]
    assert st["flag_x"] == 3168 and st["width"] == 3168 and st["time_limit"] == 400 and not st["hard_mode"]
    assert [(p["x"], p["height"], p["enterable"]) for p in a["pipes"]][:4] == [(448, 2, False), (608, 3, False), (736, 4, False), (912, 4, True)]
    assert st["pipe_exits"] == [{"area": "ground6", "x": 912, "row": 7, "to": "underground3", "entrance_page": 0}]
    blocks = {(b["x"], b["row"]): b for b in a["blocks"]}
    assert blocks[(256, 7)]["contents"] == "coin" and blocks[(336, 7)]["contents"] == "power-up"           # the first ? blocks
    hidden = blocks[(1024, 6)]
    assert hidden["contents"] == "1-up" and hidden["hidden"] and hidden["only_if"] == "hidden_1up_flag"   # the hidden 1-up
    assert [(e["type"], e["x"]) for e in a["enemies"] if e["type"] == "goomba"][0] == ("goomba", 352)
    assert [g["x"] for g in a["gaps"]] == [1104, 1376, 2448] and [g["w"] for g in a["gaps"]] == [32, 48, 32]
    assert [s["columns"] for s in a["stairs"]] == [4, 4, 9] and a["stairs"][2]["heights"][-1] == 8
    assert st["summary"]["block_contents"] == {"1-up": 1, "coin": 10, "multi-coin": 1, "power-up": 3, "star": 1}
    assert not any(e["type"] == "piranha_plant" and not e.get("from_pipe") for e in a["enemies"])
    assert st["no_pipe_piranha"] and "piranha_plant" not in st["summary"]["enemy_types"]                  # 1-1 has none


def test_1_2_has_its_mushroom_block_moving_platforms_and_the_warp_zone(db):
    st, a = db["stages"]["1-2"], db["areas"]["underground1"]
    mushroom = [b for b in a["blocks"] if (b["x"], b["row"]) == (160, 7)][0]
    assert mushroom["block"] == "question" and mushroom["contents"] == "power-up" and not mushroom["hidden"]
    assert {p["type"] for p in a["platforms"]} == {"large_lift_down", "large_lift_up"} and len(a["platforms"]) == 4
    assert st["warp_zone"] and [(w["x"], w["to_world"]) for w in st["warp_pipes"]] == [(2848, 4), (2912, 3), (2976, 2)]
    assert [x["key"] + ":" + x["role"] for x in st["areas"]] == ["ground10:intro", "underground1:main", "underground3:sub", "ground6:end"]
    assert st["end"] == {"area": "ground6", "x": 3168, "kind": "flagpole"}           # 1-2 ends in the flagpole screen of the 1-1 block
    assert st["summary"]["block_contents"]["star"] == 1 and "power-up" in st["summary"]["block_contents"]


def test_other_known_facts(db):
    st = db["stages"]
    assert [w["to_world"] for w in st["4-2"]["warp_pipes"]] == [5, 8, 7, 6]                 # 4-2: the pipe to 5, and the 8-7-6 zone
    assert st["8-1"]["hard_mode"] and not st["4-4"]["hard_mode"] and st["5-3"]["hard_mode"] and not st["5-2"]["hard_mode"]
    assert any(f["type"] == "long_firebar" for f in db["areas"]["castle3"]["firebars"])
    assert {p["type"] for p in db["areas"]["ground13"]["platforms"]} >= {"balance_lift", "vertical_platform"}
    assert db["areas"]["castle2"]["castle_bridge"] and any(e["type"] == "bowser" for e in db["areas"]["castle1"]["enemies"])
    assert db["areas"]["water2"]["area_type"] == "water" and db["stages"]["2-2"]["end"]["area"] == "ground6"
    for k in ("castle1", "castle2", "castle3", "castle4", "castle5", "castle6"):
        assert db["areas"][k]["axe"] and any(g["kind"] == "lava" for g in db["areas"][k]["gaps"]) or k == "castle6"
    assert any(c["style"] == "mushroom" for c in db["areas"]["ground13"]["ledges"])
    assert len(db["areas"]["ground20"]["cannons"]) == 13 and len(db["areas"]["ground8"]["bridges"]) == 14


def test_enemy_stream_skips_entries_the_game_skips(db):
    """2-2's blooper at x=1136 comes after a hard-mode entry at x=1232: the game never spawns it (checked on the emulator)."""
    bl = [e for e in db["areas"]["water2"]["enemies"] if e["type"] == "blooper" and e["x"] == 1136]
    assert bl and bl[0].get("never_spawns")
    assert all("never_spawns" not in e for e in db["areas"]["ground6"]["enemies"])


def test_solid_masks_cover_the_area_and_floor_runs_and_gaps_tile_it(db):
    for key, a in db["areas"].items():
        cols = len(a["solid"]) // 4
        runs = a["ground_runs"] + a["gaps"]
        assert sum(r["w"] for r in runs) == cols * 16, key                  # every column is a floor run or a gap
        masks = [int(a["solid"][i:i + 4], 16) for i in range(0, len(a["solid"]), 4)]
        for g in a["gaps"]:
            assert not any(masks[c] & 0x1800 for c in range(g["x"] // 16, (g["x"] + g["w"]) // 16)), key


def test_the_committed_file_is_what_the_rom_gives():
    spec = importlib.util.spec_from_file_location("read_rom_levels", ROOT / "tools" / "read_rom_levels.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert leveldata.DB_PATH.read_text(encoding="utf-8") == mod.dumps(build.build()) + "\n"


def test_rom_tables_are_found_and_every_block_decodes():
    rom = R.load()
    assert len(rom.area_ptr) == len(rom.enemy_ptr) == 34 and rom.area_pointer(0, 0) == 0x25 and rom.area_pointer(7, 3) == 0x65
    for typ, n in enumerate(R.TYPE_COUNTS):
        for idx in range(n):
            _, _, ecpu, acpu = rom.locate(typ << 5 | idx)
            assert A.read_header(rom, acpu)["timer_code"] in (0, 1, 2, 3) and A.read_objects(rom, acpu)


def test_level_catalogue_reads_the_db(db):
    from fly_mario.runner import level_catalogue
    cat = {c.id: c for c in level_catalogue()}
    assert cat["1-2"].contents["power-up"] >= 1 and "mushroom" in cat["1-2"].objects and cat["1-2"].source == "rom"
    assert cat["1-1"].width == cat["1-1"].flag_x == db["stages"]["1-1"]["flag_get_x"] == 3161 and cat["1-4"].flag_x == 2263 and cat["1-4"].kind == "castle" and cat["1-3"].kind == "athletic"
    assert "piranha" not in cat["1-1"].objects and "piranha" in cat["1-2"].objects
    assert json.dumps(db)                                                       # plain JSON
