"""bridge/motor.py -- which button a motor command presses. Re-exports
mario.actions.actions.action_index as the bridge boundary."""

from __future__ import annotations

from mario.actions.actions import action_index

__all__ = ["action_index"]
