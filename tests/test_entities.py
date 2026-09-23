# What this file does, in plain English:
# Checks the code that labels things found in the game's memory: which byte
# means a Goomba, a Koopa or a power-up, what each enemy slot holds, which
# map tiles are ground, blocks or empty, and when a pit lies ahead. It also
# checks every kind of thing has an entry in the default profile file. These
# small tests pinpoint a break that the full-game tests would not.
"""
Unit coverage for mario/entities/. The goldens only reach KindRegistry
through a full episode and would not localise a break to this module.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mario.entities.kinds import EntityKind, Trait
from mario.entities.registry import (
    DEFAULT as registry, ENTITY_WIDTH_PX, GOOMBA_TYPE_BYTE, KOOPA_TYPE_BYTE,
)
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, N_ENEMY_SLOTS, POWERUP_ID,
)
from mario.ram import tile_ram

PROFILE_PATH = Path(__file__).parent.parent / "bridge" / "profiles" / "default.json"


def _fake_ram(size=0x800):
    return np.zeros(size, dtype=np.uint8)


def test_enemy_kind_matches_the_old_bare_comparison():
    """Phase 4: 0x00/0x06 are now real species (screenshot-verified,
    docs/ENTITIES.md), not generic ENEMY -- but bridge/perception.py's
    own `!= POWERUP` checks never depended on which specific non-powerup
    kind something is, so this split is behaviour-preserving. 0x02 stands
    in for "some byte this project hasn't identified yet"."""
    assert registry.enemy_kind(POWERUP_ID) == EntityKind.POWERUP
    assert registry.enemy_kind(KOOPA_TYPE_BYTE) == EntityKind.KOOPA
    assert registry.enemy_kind(GOOMBA_TYPE_BYTE) == EntityKind.GOOMBA
    assert registry.enemy_kind(0x02) == EntityKind.ENEMY


def test_enemy_records_reproduces_slot_layout():
    ram = _fake_ram()
    ram[ADDR_ENEMY_ACTIVE + 0] = 1
    ram[ADDR_ENEMY_TYPE + 0] = POWERUP_ID
    ram[ADDR_ENEMY_X + 0] = 200
    ram[ADDR_ENEMY_ACTIVE + 1] = 1
    ram[ADDR_ENEMY_TYPE + 1] = GOOMBA_TYPE_BYTE
    ram[ADDR_ENEMY_X + 1] = 50

    records = registry.enemy_records(ram)
    assert len(records) == N_ENEMY_SLOTS
    assert records[0].active and records[0].kind == EntityKind.POWERUP
    assert records[0].x == 200 and records[0].width == ENTITY_WIDTH_PX
    assert Trait.COLLECTIBLE in records[0].traits
    assert records[1].active and records[1].kind == EntityKind.GOOMBA
    assert Trait.THREAT in records[1].traits
    assert not records[2].active  # untouched slot


def test_tile_kind_matches_tile_ram_constants():
    assert registry.tile_kind(tile_ram.GROUND_ID) == EntityKind.GROUND
    assert registry.tile_kind(tile_ram.QUESTION_COIN_ID) == EntityKind.QUESTION_BLOCK
    assert registry.tile_kind(tile_ram.QUESTION_POWERUP_ID) == EntityKind.QUESTION_BLOCK
    assert registry.tile_kind(tile_ram.USED_BLOCK_ID) == EntityKind.USED_BLOCK
    assert registry.tile_kind(tile_ram.EMPTY_ID) == EntityKind.EMPTY
    assert registry.tile_kind(0x51) == EntityKind.SOLID_OTHER  # a brick, e.g.


def test_pit_record_none_when_ground_ahead():
    ram = _fake_ram()
    # ground row filled with GROUND_ID for every column solid_ahead/gap_width look at
    ram[tile_ram.BUF1_ADDR + tile_ram.GROUND_ROW * tile_ram.COLS:
        tile_ram.BUF1_ADDR + (tile_ram.GROUND_ROW + 1) * tile_ram.COLS] = tile_ram.GROUND_ID
    ram[tile_ram.BUF2_ADDR + tile_ram.GROUND_ROW * tile_ram.COLS:
        tile_ram.BUF2_ADDR + (tile_ram.GROUND_ROW + 1) * tile_ram.COLS] = tile_ram.GROUND_ID
    assert registry.pit_record(ram, mario_x=40) is None


def test_pit_record_present_over_a_gap():
    ram = _fake_ram()  # all-zero == EMPTY_ID everywhere -- a gap by construction
    rec = registry.pit_record(ram, mario_x=40)
    assert rec is not None
    assert rec.kind == EntityKind.PIT
    assert rec.width > 0 and rec.width % 16 == 0
    assert Trait.LETHAL_ON_CONTACT in rec.traits


def test_default_profile_covers_every_kind_the_registry_assigns():
    profile = json.loads(PROFILE_PATH.read_text())
    kinds_with_profiles = {k for k in profile if not k.startswith("_")}
    # every EntityKind the registry can actually assign should have a
    # profile entry, except EMPTY -- the absence of a tile, not an entity.
    for kind in EntityKind:
        if kind is EntityKind.EMPTY:
            continue
        assert kind.name in kinds_with_profiles, f"{kind.name} has no bridge/profiles/default.json entry"
