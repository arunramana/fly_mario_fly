"""sim/episode.py -- REFACTOR_PLAN.md section 5.2: "Episode composes a
Policy and an Environment and knows nothing else... Telemetry becomes an
observer the episode notifies."

Deliberately generic: this file imports nothing from fly/, mario/, or
bridge/ -- tests/test_import_guard.py enforces that by AST, the same way
it already enforces fly/ never importing mario/bridge. `Episode` doesn't
know what a `theta` or a `press_a` is; it only knows it has a `Policy`, an
`Environment`, and some observers to tell "a step happened."

Not yet wired to run_steering.py's actual full system (jump/steering/
terrain/mushroom-body/habituation/MDN) -- that migration is real,
substantial work of its own and is deliberately deferred (docs/RUNS.md's
phase 5 note has the scoping reasoning). `run_steering.main()` remains
today's actual entry point for a full scenario; this class is real,
tested, working infrastructure for whoever migrates a Policy onto it next,
proven end-to-end with a real concrete Policy/Environment pair
(bridge/policy.py's `JumpPolicy`, mario/emulator/environment.py's
`MarioEnvironment`) rather than a toy.
"""

from __future__ import annotations

from typing import Protocol

from sim.protocols import Action, Environment, Observation, Policy


class EpisodeObserver(Protocol):
    def on_step(self, step: int, observation: Observation, action: Action) -> None: ...
    def on_episode_end(self, steps: int) -> None: ...


class Episode:
    def __init__(self, policy: Policy, environment: Environment, observers=()):
        self.policy = policy
        self.environment = environment
        self.observers = list(observers)

    def run(self, seed: int, max_steps: int) -> Observation:
        observation = self.environment.reset(seed)
        self.policy.reset(seed)
        step = 0
        for step in range(max_steps):
            action = self.policy.act(observation)
            observation = self.environment.step(action)
            for observer in self.observers:
                observer.on_step(step, observation, action)
            # A soft, generic duck-type check, not a protocol requirement --
            # Episode still imports nothing from any concrete Observation's
            # own module. An Observation with no `.done` (or a falsy one)
            # simply runs the full max_steps, exactly as before this check
            # existed.
            if getattr(observation, "done", False):
                break
        for observer in self.observers:
            observer.on_episode_end(step + 1)
        return observation
