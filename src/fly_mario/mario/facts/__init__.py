"""Facts about the game: RAM addresses, tile ids, sizes. Loaded from yaml, never hard-coded in .py files."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).parent


class Facts(dict):
    """A nested dict with attribute access: facts.ram['mario_x'], facts.grid['tile']."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key) from None


def _merge(base: dict, extra: dict) -> dict:
    """Maps are merged, lists are appended (no duplicates), anything else is replaced."""
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        elif isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = out[k] + [x for x in v if x not in out[k]]
        else:
            out[k] = v
    return out


@lru_cache(maxsize=None)
def load_facts(level_id: str = "1-1") -> Facts:
    """smb1.yaml, extended by levels/<level_id>.yaml when that file exists."""
    data = yaml.safe_load((HERE / "smb1.yaml").read_text(encoding="utf-8"))
    extra = HERE / "levels" / f"{level_id}.yaml"
    if extra.exists():
        data = _merge(data, yaml.safe_load(extra.read_text(encoding="utf-8")))
    data["level_id"] = level_id
    return Facts(data)
