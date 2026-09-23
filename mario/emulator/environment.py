# What this file does, in plain English:
# Wraps the game emulator in a small object that can start a level, advance
# one frame for a chosen button press, and shut down. After each step it
# hands back a copy of the game's memory and whether the game has ended. It
# is used by the test tests/test_episode.py; the main run script
# (run_steering.py) drives the emulator directly instead.
"""mario/emulator/environment.py -- a concrete sim.protocols.Environment,
wrapping nes-py/gym_super_mario_bros directly (via mario.emulator.env's
existing make_env). Generic to any policy -- takes an integer action index
(mario.actions.actions.action_index's own encoding) and returns a
MarioObservation carrying the raw RAM array plus whether the episode has
ended. No fly/bridge dependency.

run_steering.main() drives nes-py directly; this class is used by
tests/test_episode.py.
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
        """`seed` is ignored: the protocol requires it, but SMB has no
        seedable RNG we use."""
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
