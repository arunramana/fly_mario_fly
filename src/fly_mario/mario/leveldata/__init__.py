"""The level database: every stage and area of SMB1, read once from the ROM (tools/read_rom_levels.py) into
mario/facts/level_db.json. This package reads that file; build.py/areas.py/enemies.py/rom.py are only needed to make it."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "facts" / "level_db.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def available() -> bool:
    return DB_PATH.exists()


def stage(level_id: str) -> dict | None:
    """The stage entry for "1-1" ... "8-4", or None for the whole-game envs."""
    return load()["stages"].get(level_id)


def area(key: str) -> dict:
    return load()["areas"][key]


def stage_areas(level_id: str) -> list:
    """[(role, area dict)] of the stage, main area first among the playable ones."""
    st = stage(level_id)
    return [(a["role"], area(a["key"])) for a in st["areas"]] if st else []
