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
