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


def group_types(group_names) -> tuple:
    """The cell types named by `types:` of these groups, in groups.yaml order, each once."""
    want, out = set(group_names), []
    for n, g in load_groups().items():
        out += [t for t in g.types if n in want and t not in out]
    return tuple(out)


@lru_cache(maxsize=1)
def type_counts() -> dict:
    """{cell type: verified neuron count}; every key is a `types:` entry of some group (ORN_DC4 has no count: the
    aversion mechanism checks its own 13)."""
    counts = dict(_table()["type_counts"])
    stray = set(counts) - set(group_types(load_groups()))
    assert not stray, f"groups.yaml type_counts names types no group uses: {sorted(stray)}"
    return counts


def other_colour() -> str:
    return _table()["other_colour"]


def masks_for(types: np.ndarray, sides: np.ndarray) -> dict:
    """{group name: boolean mask}, only for groups with at least one neuron in this brain."""
    types, sides = np.asarray(types, dtype="U40"), np.asarray(sides, dtype="U40")
    out = {n: g.mask(types, sides) for n, g in load_groups().items()}
    return {n: m for n, m in out.items() if m.any()}
