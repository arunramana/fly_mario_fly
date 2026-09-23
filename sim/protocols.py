# What this file does, in plain English:
# Describes, without any working code, the two shapes the game loop in
# episode.py expects: a "policy" that picks an action from what it
# observes, and an "environment" (the game) that takes an action and
# returns what happens next. Both can be reset with a random seed. The real
# versions live elsewhere, in bridge/ and mario/.
"""sim/protocols.py -- the Policy and Environment protocols Episode
composes. bridge/ supplies the policies and mario/ the environment; neither
is imported here (tests/test_import_guard.py).
"""

from __future__ import annotations

from typing import Any, Protocol

Action = Any
Observation = Any


class Policy(Protocol):
    def act(self, observation: Observation) -> Action: ...
    def reset(self, seed: int) -> None: ...


class Environment(Protocol):
    def step(self, action: Action) -> Observation: ...
    def reset(self, seed: int) -> Observation: ...
