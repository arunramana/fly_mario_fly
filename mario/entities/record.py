# What this file does, in plain English:
# Defines a small fixed record describing one thing in the game: what kind
# it is, where it is, how wide and tall it is, whether it is currently
# present, and its labels (threat, collectible, and so on). It only holds
# this information; it has no behaviour of its own.
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
