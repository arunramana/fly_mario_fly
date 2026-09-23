"""mario/entities/record.py -- REFACTOR_PLAN.md section 4.

EntityRecord is a frozen value object, not a class tree: we do not simulate
Goombas, Koopas or pits -- nes-py simulates the game, we only read RAM (or,
for a pit, the absence of a tile), so an entity has no methods and no
behaviour of its own. `kind` and `traits` carry all the variation; a new
entity with an unusual trait mix needs no new class, just a new
KindRegistry entry.

`x`/`width` are in the same screen-relative pixel units ADDR_MARIO_X and
ADDR_ENEMY_X already use -- `x - mario_x` reproduces exactly the distance
every odour/looming function in bridge/perception.py was already computing
before this record existed.
"""

from __future__ import annotations

from dataclasses import dataclass

from mario.entities.kinds import EntityKind, Trait


@dataclass(frozen=True)
class EntityRecord:
    kind: EntityKind
    x: float
    y: float | None
    width: int
    height: int | None
    active: bool
    traits: frozenset[Trait]
