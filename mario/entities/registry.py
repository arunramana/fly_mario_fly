"""mario/entities/registry.py -- maps RAM type bytes to entity kinds, traits
and dimensions. Every "is this enemy slot a powerup or a threat" question
goes through `enemy_records()`. Tile IDs stay in mario.ram.tile_ram and are
referenced, not copied.
"""

from __future__ import annotations

from mario.entities.kinds import EntityKind, Trait
from mario.entities.record import EntityRecord
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_ENEMY_Y,
    N_ENEMY_SLOTS, POWERUP_ID,
)

# Every enemy-slot occupant is assumed 16px wide. Real SMB hitboxes differ
# by species; that is not modelled (docs/ENTITIES.md).
ENTITY_WIDTH_PX = 16

# Confirmed by screenshotting the frame each type byte first appeared in a
# bot-driven 1-1/1-2 playthrough (docs/ENTITIES.md has the survey).
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
    """Stateless; methods take the `ram` array. DEFAULT is the shared
    instance."""

    def traits_of(self, kind: EntityKind) -> frozenset[Trait]:
        return _KIND_TRAITS[kind]

    def enemy_kind(self, type_byte: int) -> EntityKind:
        """GOOMBA/KOOPA where verified; any other non-powerup byte is
        generic ENEMY."""
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
        """A named kind for a raw tile byte. tile_ram's own functions use
        its constants directly, not this."""
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
        """A pit, synthesised from missing ground tiles: a looming detector
        cannot see one (docs/RUNS.md 004). `width` is in pixels. Not yet
        used by the decision loop (docs/ENTITIES.md)."""
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
