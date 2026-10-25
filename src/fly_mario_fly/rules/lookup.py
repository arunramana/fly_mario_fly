"""Find a plug-in's DECLARATION by kind and name (used by the runner's guards and by tools)."""
from __future__ import annotations

from functools import lru_cache

from fly_mario_fly import registry


@lru_cache(maxsize=None)
def _modules(kind: str) -> dict:
    return registry.list_modules(kind)


def declaration_of(kind: str, name: str):
    """The Declaration of the plug-in `name` in the registry kind `kind` ("senses", "actions", ...)."""
    return _modules(kind)[name].DECLARATION
