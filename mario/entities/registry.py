"""mario/entities/registry.py -- REFACTOR_PLAN.md section 4: "A KindRegistry
maps RAM type bytes to kinds and their intrinsic dimensions -- the single
home for ROM facts, which today are scattered across enemy_thetas() and the
tile decoder."

Before this module, "is this enemy slot a powerup or a threat" was answered
by an identical `ram[ADDR_ENEMY_TYPE + i] == POWERUP_ID` comparison written
independently three times: run_mario.py's enemy_thetas, run_steering.py's
mushroom_odor, run_steering.py's goomba_odor. All three now go through
`enemy_records()` below. See docs/ENTITIES.md and docs/REFACTOR_PLAN.md's
phase 2 report for the full duplication writeup, including the ROM facts
this module does NOT yet unify (tile_ram.py's own tile-id constants stay
tile_ram.py's, referenced here rather than redefined).

Tile IDs are looked up on demand from mario.ram.tile_ram's own module-level
constants rather than copied -- that module is already a correct single
source of truth for them, just not one shaped like a registry.
"""

from __future__ import annotations

from mario.entities.kinds import EntityKind, Trait
from mario.entities.record import EntityRecord
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_ENEMY_Y,
    N_ENEMY_SLOTS, POWERUP_ID,
)

# Every enemy-slot occupant this project has ever driven a looming or odour
# calculation from is assumed exactly this wide -- run_mario.py's W_TILE and
# sensory.py's W_TILE both already carried this same value independently.
# A real Goomba/Koopa/Piranha/mushroom do not actually share one hitbox
# width in SMB; this project has simply never modeled the difference. Kept
# exactly as before -- giving it a home, not fixing it (docs/ENTITIES.md).
ENTITY_WIDTH_PX = 16

# Phase 4: empirically confirmed by playing 1-1/1-2 (bot-driven, since the
# real circuit dies before reaching much of either level) and screenshotting
# the frame each new ADDR_ENEMY_TYPE byte first appeared -- same standard
# tile_ram.py's own tile IDs were held to, not trusted from memory or a web
# table. See docs/ENTITIES.md's phase 4 report for the full survey
# (frame numbers, positions, and which byte was screenshotted where).
GOOMBA_TYPE_BYTE = 0x06
KOOPA_TYPE_BYTE = 0x00
_SPECIES_BY_TYPE_BYTE: dict[int, EntityKind] = {
    GOOMBA_TYPE_BYTE: EntityKind.GOOMBA,
    KOOPA_TYPE_BYTE: EntityKind.KOOPA,
}

_KIND_TRAITS: dict[EntityKind, frozenset[Trait]] = {
    EntityKind.GOOMBA: frozenset({Trait.THREAT, Trait.LETHAL_ON_CONTACT}),
    EntityKind.KOOPA: frozenset({Trait.THREAT, Trait.LETHAL_ON_CONTACT}),
    EntityKind.ENEMY: frozenset({Trait.THREAT, Trait.LETHAL_ON_CONTACT}),
    EntityKind.POWERUP: frozenset({Trait.COLLECTIBLE}),
    EntityKind.GROUND: frozenset({Trait.SOLID}),
    EntityKind.QUESTION_BLOCK: frozenset({Trait.COLLECTIBLE, Trait.SOLID}),
    EntityKind.USED_BLOCK: frozenset({Trait.SOLID}),
    EntityKind.EMPTY: frozenset(),
    EntityKind.PIT: frozenset({Trait.LETHAL_ON_CONTACT}),
    EntityKind.SOLID_OTHER: frozenset({Trait.SOLID}),
}


class KindRegistry:
    """Stateless -- every method takes the `ram` array it needs, matching
    every RAM-reading function in this project. One instance is enough for
    the whole process; DEFAULT below is that instance."""

    def traits_of(self, kind: EntityKind) -> frozenset[Trait]:
        return _KIND_TRAITS[kind]

    def enemy_kind(self, type_byte: int) -> EntityKind:
        """Phase 4: real per-species decoding for the two kinds confirmed
        present in 1-1/1-2 (GOOMBA/KOOPA, see docs/ENTITIES.md); any other
        non-powerup byte falls back to generic ENEMY -- discrimination is
        possible where it's been verified, not assumed where it hasn't."""
        if type_byte == POWERUP_ID:
            return EntityKind.POWERUP
        return _SPECIES_BY_TYPE_BYTE.get(type_byte, EntityKind.ENEMY)

    def enemy_record(self, ram, slot: int) -> EntityRecord:
        active = bool(ram[ADDR_ENEMY_ACTIVE + slot])
        kind = self.enemy_kind(int(ram[ADDR_ENEMY_TYPE + slot]))
        return EntityRecord(
            kind=kind,
            x=int(ram[ADDR_ENEMY_X + slot]),
            y=int(ram[ADDR_ENEMY_Y + slot]),
            width=ENTITY_WIDTH_PX,
            height=None,
            active=active,
            traits=self.traits_of(kind),
        )

    def enemy_records(self, ram) -> list[EntityRecord]:
        return [self.enemy_record(ram, i) for i in range(N_ENEMY_SLOTS)]

    def tile_kind(self, tile_id: int) -> EntityKind:
        """A real EntityKind view onto tile_ram.py's own already-correct
        constants -- provided for anyone (a future GUI, bridge/perception.py)
        that wants a named kind rather than a raw byte. tile_ram.py's own
        four analysis functions (ground_ahead/gap_width/solid_ahead/
        question_blocks_near) keep using their own constants directly and
        are NOT rewritten to call this -- they are already a single,
        correct home for these facts, just not one shaped like a registry.
        See docs/ENTITIES.md for that scoping decision."""
        if tile_id == tile_ram.GROUND_ID:
            return EntityKind.GROUND
        if tile_id in tile_ram.QUESTION_IDS:
            return EntityKind.QUESTION_BLOCK
        if tile_id == tile_ram.USED_BLOCK_ID:
            return EntityKind.USED_BLOCK
        if tile_id == tile_ram.EMPTY_ID:
            return EntityKind.EMPTY
        return EntityKind.SOLID_OTHER

    def pit_record(self, ram, mario_x) -> EntityRecord | None:
        """SPEC_terrain.md's pit, given a first-class record per REFACTOR_
        PLAN.md section 4: "Pit is synthesised from missing tiles... 004
        established a looming detector structurally cannot see it -- which
        is exactly why it needs a first-class record." `width` is in
        pixels (tile_ram.gap_width's tile count * 16), matching every other
        EntityRecord's units. Not yet a call site anywhere in main()'s
        decision loop -- that integration is deferred, stated in
        docs/ENTITIES.md rather than left to look finished when it isn't."""
        width_tiles = tile_ram.gap_width(ram)
        if width_tiles == 0:
            return None
        return EntityRecord(
            kind=EntityKind.PIT,
            x=int(mario_x) + 16,
            y=None,
            width=width_tiles * 16,
            height=None,
            active=True,
            traits=self.traits_of(EntityKind.PIT),
        )


DEFAULT = KindRegistry()
