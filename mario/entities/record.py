"""mario/entities/record.py -- EntityRecord, a frozen value object rather
than a class tree: nes-py simulates the game and we only read RAM, so an
entity has no behaviour of its own. `kind` and `traits` carry all the
variation.

`x`/`width` are screen-relative pixels, the units of ADDR_MARIO_X, so
`x - mario_x` is the distance bridge/perception.py uses.
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
