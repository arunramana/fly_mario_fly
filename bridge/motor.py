# What this file does, in plain English:
# Gives the bridge its own name for the function that turns a direction
# plus two button choices (jump and run) into a game button press. The
# function itself lives in mario/actions/actions.py; this file only passes it
# on and adds no code of its own.
"""bridge/motor.py -- which button a motor command presses. Re-exports
mario.actions.actions.action_index as the bridge boundary."""

from __future__ import annotations

from mario.actions.actions import action_index

__all__ = ["action_index"]
