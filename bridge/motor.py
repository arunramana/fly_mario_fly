"""bridge/motor.py -- REFACTOR_PLAN.md section 2: the second of bridge/'s
two questions, "what button does this motor command press?" The actual
encoding (direction + press_a + press_b -> MOVES index) already existed as
mario.actions.actions.action_index and needed no change -- this re-exports
it as the named bridge boundary rather than duplicating it, since it was
already exactly the function this module's job description describes."""

from __future__ import annotations

from mario.actions.actions import action_index

__all__ = ["action_index"]
