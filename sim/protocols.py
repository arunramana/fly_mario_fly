"""sim/protocols.py -- REFACTOR_PLAN.md section 5.2, verbatim:

    class Policy(Protocol):
        def act(self, observation) -> Action: ...
        def reset(self, seed: int) -> None: ...

    class Environment(Protocol):
        def step(self, action) -> Observation: ...
        def reset(self, seed: int) -> Observation: ...

`Episode` (episode.py, this package) composes one of each and knows
nothing else -- no fly/mario/bridge import anywhere in this file or in
episode.py, enforced by tests/test_import_guard.py. `bridge/policy.py`
supplies the concrete fly-backed `Policy`; `mario/`'s environment supplies
the concrete `Environment`. Neither concrete class is imported here --
that would defeat the whole point of a Protocol boundary.
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
