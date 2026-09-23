# What this file does, in plain English:
# Defines a basic game loop: at each step the decision-maker (a "policy")
# picks a button press, the game advances one step, and any attached
# listeners are told what happened. It stops early when the game reports
# the run is over. It never imports the fly, game or bridge code; the tests
# use it, while run_steering.py runs its own loop instead.
"""sim/episode.py -- composes a Policy and an Environment and notifies
observers each step. Imports nothing from fly/, mario/ or bridge/
(tests/test_import_guard.py enforces it).

run_steering.main() drives FullPolicy from its own loop rather than
through Episode; Episode is exercised with JumpPolicy in
tests/test_episode.py.
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
            # Duck-typed: an Observation without `.done` runs to max_steps.
            if getattr(observation, "done", False):
                break
        for observer in self.observers:
            observer.on_episode_end(step + 1)
        return observation
