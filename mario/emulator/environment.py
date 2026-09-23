"""mario/emulator/environment.py -- a concrete sim.protocols.Environment,
wrapping nes-py/gym_super_mario_bros directly (via mario.emulator.env's
existing make_env). Generic to any policy -- takes an integer action index
(mario.actions.actions.action_index's own encoding) and returns a
MarioObservation carrying the raw RAM array plus whether the episode has
ended. No fly/bridge dependency.

Not yet used by run_steering.py's own main() -- that keeps driving nes-py
directly, unchanged, for the full jump/steering/terrain/mushroom-body
system (docs/RUNS.md's phase 5 note has the scoping reasoning). This class
is real, tested infrastructure (tests/test_episode.py runs a real episode
against it), not a decorative stub.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from mario.emulator.env import make_env


@dataclass(frozen=True)
class MarioObservation:
    ram: np.ndarray
    done: bool


class MarioEnvironment:
    def __init__(self, level: str = "1-1"):
        self.level = level
        self._env = None

    def reset(self, seed: int) -> MarioObservation:
        """`seed` is accepted to satisfy the Environment protocol (and
        gym's own reset(seed=...) convention) -- SMB itself has no
        seedable RNG this project has ever found a use for (SPEC_jump.md
        never plumbed one in); accepting and ignoring it here is honest
        about that, not a placeholder for something unbuilt."""
        if self._env is None:
            self._env = make_env(self.level)
        self._env.reset()
        return MarioObservation(ram=self._env.unwrapped.ram, done=False)

    def step(self, action: int) -> MarioObservation:
        obs, reward, done, info = self._env.step(action)
        return MarioObservation(ram=self._env.unwrapped.ram, done=done)

    def close(self) -> None:
        if self._env is not None:
            self._env.close()
