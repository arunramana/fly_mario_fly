# What this file does, in plain English:
# Starts the Super Mario Bros game emulator (a program that runs the
# original NES game) on a chosen level such as "1-1", and limits its
# controller to the button combinations in mario/actions/actions.py (all 64;
# the first eight are the original ones, so their indices are unchanged).
"""mario/emulator/env.py -- nes-py/gym-super-mario-bros env construction."""

from __future__ import annotations

import setuptools  # noqa: F401  -- must import before gym on py3.12 (distutils shim)
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

from mario.actions.actions import MOVES_ALL


def make_env(level="1-1"):
    env = gym_super_mario_bros.make(f"SuperMarioBros-{level}-v0")
    return JoypadSpace(env, MOVES_ALL)
