"""mario/entities/kinds.py -- REFACTOR_PLAN.md section 4, extended in
phase 4 with real per-species decoding.

Phase 2 found this codebase had never read ADDR_ENEMY_TYPE for anything
except "is it the one powerup ID" -- every real enemy was the same ENEMY
kind. Phase 4 gives KindRegistry real species: GOOMBA and KOOPA, the two
confirmed present in 1-1/1-2 (docs/ENTITIES.md's phase 4 report has the
empirical survey and screenshot-verified evidence, same standard
mario/ram/tile_ram.py's own tile IDs were held to -- not trusted from a
web table or from memory). ENEMY remains as the fallback for any type
byte this project has not yet identified -- discrimination is now
POSSIBLE, not exhaustive: 1-1/1-2 were surveyed only as far as a real or
bot-driven playthrough could reach, not their full length, so a species
this project hasn't encountered yet would still classify as generic
ENEMY, correctly rather than incorrectly.
"""

from __future__ import annotations

import enum


class EntityKind(enum.Enum):
    GOOMBA = "goomba"            # ADDR_ENEMY_TYPE==0x06, screenshot-verified, phase 4 (docs/ENTITIES.md)
    KOOPA = "koopa"              # ADDR_ENEMY_TYPE==0x00, screenshot-verified, phase 4 (docs/ENTITIES.md)
    ENEMY = "enemy"              # any other active, non-powerup enemy-slot occupant -- not yet identified
    POWERUP = "powerup"          # mushroom/flower/star/1-up -- same slots, ADDR_ENEMY_TYPE==POWERUP_ID
    GROUND = "ground"            # tile_ram.GROUND_ID
    QUESTION_BLOCK = "question_block"  # tile_ram.QUESTION_IDS (coin or power-up, not distinguished)
    USED_BLOCK = "used_block"    # tile_ram.USED_BLOCK_ID -- a question block already hit
    EMPTY = "empty"              # tile_ram.EMPTY_ID -- sky, or a pit tile
    PIT = "pit"                  # synthesised from a run of EMPTY ground tiles, no RAM slot of its own
    SOLID_OTHER = "solid_other"  # brick/pipe/anything else tile_ram.solid_ahead treats as a wall


class Trait(enum.Enum):
    THREAT = "threat"                    # drives looming (bridge.perception) and aversive odour
    COLLECTIBLE = "collectible"          # drives attractive odour, hunger-gated
    SOLID = "solid"                      # blocks forward movement -- the climb reflex's trigger
    LETHAL_ON_CONTACT = "lethal_on_contact"  # true of every real SMB enemy and every real pit;
                                              # nes-py's own engine enforces this, not this project's
                                              # code -- named here because a GUI binding to traits
                                              # needs the fact, even though nothing here re-implements it
