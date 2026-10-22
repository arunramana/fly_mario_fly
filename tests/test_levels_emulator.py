"""The level database against the emulator (tools/verify_rom_levels.py carries Mario through a level, enemies swept, and compares):
the tile buffer with the db's solid masks, every enemy / lift / fire bar the game spawns with the db's list, the flag with the db's
flag x. Slow-ish (each level is a few thousand frames), so a handful of levels: ground, castle, athletic with lifts, water."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def verify():
    spec = importlib.util.spec_from_file_location("verify_rom_levels", ROOT / "tools" / "verify_rom_levels.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("level,frames", [("1-1", 4000), ("1-4", 4000), ("1-3", 4000)])
def test_db_matches_the_emulator_to_the_flag(verify, level, frames):
    r = verify.run_level(level, frames)
    assert r["stop"] == "flag", r["last"]                                      # Mario got to the flag / axe
    assert r["n_tile_mismatches"] == 0, r["tile_mismatches"]
    assert not r["missing"] and r["n_extra"] == 0, (r["missing"], r["extra"])
    assert r["matched"] == r["expected"] > 0
    assert abs(r["emulator_flag_x"] - r["db_flag_get_x"]) <= 8                # the game's flag_get x vs the db's


def test_3_3_and_5_3_match_up_to_the_flag(verify):
    for level in ("3-3", "5-3"):                    # (the walker may die near the end, so only the part it reached is compared)
        r = verify.run_level(level, 4000, stop_before_flag=True)
        assert r["max_x"] > 2000 and r["n_tile_mismatches"] == 0, (level, r["stop"], r["tile_mismatches"])
        assert not r["missing"] and r["n_extra"] == 0 and r["matched"] == r["expected"] > 5, (level, r["missing"], r["extra"])


def test_1_2_and_2_2_match_as_far_as_mario_gets(verify):
    for level in ("1-2", "2-2"):
        r = verify.run_level(level, 3000)
        assert r["max_x"] > 1500 and r["n_tile_mismatches"] == 0, (level, r["tile_mismatches"])
        assert not r["missing"] and r["n_extra"] == 0, (level, r["missing"], r["extra"])


def test_block_contents_match_what_the_game_gives():
    spec = importlib.util.spec_from_file_location("verify_block_contents", ROOT / "tools" / "verify_block_contents.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mushroom = mod.hit("1-2", 160, 7)                                           # 1-2's first ? block holds the power-up
    assert mushroom["powerup"] == {"object": 0x2E, "power_type": 0} and mushroom["coins"] == 0
    assert mod.hit("1-1", 256, 7)["coins"] == 1                                  # the first ? block of 1-1: a coin
    assert mod.hit("1-1", 1616, 7)["powerup"]["power_type"] == 2                 # the brick with the star
    assert mod.hit("1-1", 1024, 6)["powerup"]["power_type"] == 3                 # the hidden 1-up
