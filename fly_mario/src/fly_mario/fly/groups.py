"""Neuron groups from groups.yaml: which brain rows belong to which named group."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

TABLE = Path(__file__).with_name("groups.yaml")


@dataclass(frozen=True)
class Group:
    name: str
    role: str
    colour: str
    types: tuple = ()
    type_prefix: str = ""
    exclude_types: tuple = ()
    side: str = ""

    def mask(self, types: np.ndarray, sides: np.ndarray) -> np.ndarray:
        m = np.isin(types, self.types)
        if self.type_prefix:
            m |= np.char.startswith(types, self.type_prefix)
        if self.exclude_types:
            m &= ~np.isin(types, self.exclude_types)
        if self.side:
            m &= sides == self.side
        return m


@lru_cache(maxsize=1)
def _table() -> dict:
    return yaml.safe_load(TABLE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_groups() -> dict:
    return {n: Group(name=n, role=g["role"], colour=g["colour"], types=tuple(g.get("types", ())),
                     type_prefix=g.get("type_prefix", ""), exclude_types=tuple(g.get("exclude_types", ())),
                     side=g.get("side", "")) for n, g in _table()["groups"].items()}


def other_colour() -> str:
    return _table()["other_colour"]


def masks_for(types: np.ndarray, sides: np.ndarray) -> dict:
    """{group name: boolean mask}, only for groups with at least one neuron in this brain."""
    types, sides = np.asarray(types, dtype="U40"), np.asarray(sides, dtype="U40")
    out = {n: g.mask(types, sides) for n, g in load_groups().items()}
    return {n: m for n, m in out.items() if m.any()}
