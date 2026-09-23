# What this file does, in plain English:
# Defines names for the kinds of things the code can recognise in the game
# (Goomba, Koopa, other enemies, power-ups, ground, "?" blocks, used blocks,
# empty space, pits, other solid tiles) and the labels those things can
# carry: a threat, something to collect, solid, or deadly to touch.
"""mario/entities/kinds.py -- entity kinds and traits.

GOOMBA and KOOPA are the species screenshot-verified in 1-1/1-2
(docs/ENTITIES.md). 1-1/1-2 were surveyed only as far as a playthrough
reached, so any other type byte falls back to generic ENEMY.
"""

from __future__ import annotations

import enum


class EntityKind(enum.Enum):
    GOOMBA = "goomba"            # ADDR_ENEMY_TYPE==0x06, screenshot-verified
    KOOPA = "koopa"              # ADDR_ENEMY_TYPE==0x00, screenshot-verified
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
    LETHAL_ON_CONTACT = "lethal_on_contact"  # every SMB enemy and pit; enforced by the game, not here
