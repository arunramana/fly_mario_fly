"""mario/entities/kinds.py -- REFACTOR_PLAN.md section 4: the vocabulary
EntityRecord and KindRegistry are built from.

Deliberately as coarse as what the running code actually discriminates
today, not as fine as SMB's real cast of characters. See docs/ENTITIES.md
for the full account of the gap between the two -- the short version is:
this project has never read the enemy-type byte for anything except "is it
the one powerup ID," so a Goomba, a Green Koopa Troopa and a Piranha Plant
are all the same ENEMY kind here, not because they're biologically alike
but because no code path distinguishes them yet.
"""

from __future__ import annotations

import enum


class EntityKind(enum.Enum):
    ENEMY = "enemy"              # any active, non-powerup enemy-slot occupant
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
