"""mario/emulator/env.py -- nes-py/gym-super-mario-bros env construction."""

from __future__ import annotations

import setuptools  # noqa: F401  -- must import before gym on py3.12 (distutils shim)
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

from mario.actions.actions import MOVES


def make_env(level="1-1"):
    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    return JoypadSpace(env, MOVES)
