"""fly/state/reflex_habituation.py -- SPEC_habituation.md section 1, moved
verbatim from run_steering.py (REFACTOR_PLAN.md phase 2). Real, documented
Giant Fiber pathway habituation, not a timeout -- fits fly/state/ alongside
hunger/arousal/satiety as a homeostatic process of the fly's own reflex
circuitry, not of Mario or the emulator. Takes plain x-progress (a float
the bridge/mario side hands it), never touches RAM directly.
"""

from __future__ import annotations

HAB_PROGRESS_PX = 16
HAB_GIVE_UP = 3


class ReflexHabituation:
    """Any reflex that keeps firing without net forward progress since the
    last time it was checked progressively suppresses itself. One instance
    per reflex (escape, climb), fully independent state.

    `last_check_x` updates every time `check()` is called, whether or not
    the reflex actually fires -- so a suppressed reflex keeps listening for
    the progress that would re-sensitise it (e.g. after MDN backs Mario up
    and a later attempt actually clears the obstacle)."""

    def __init__(self, give_up=None, progress_px=None):
        self.last_check_x = None
        self.hab_level = 0
        # read the module-level defaults at construction time, not class-
        # definition time -- a mutable default here would silently ignore
        # any later override of HAB_GIVE_UP/HAB_PROGRESS_PX (found this the
        # hard way while building the baseline-vs-fix comparison for this
        # sprint)
        self.give_up = HAB_GIVE_UP if give_up is None else give_up
        self.progress_px = HAB_PROGRESS_PX if progress_px is None else progress_px

    def check(self, mario_x) -> bool:
        """Call exactly once per frame the reflex's OWN trigger condition
        is true. Returns whether the reflex should actually fire this time
        (False once habituation has reached give_up)."""
        if self.last_check_x is not None:
            progress = mario_x - self.last_check_x
            if progress < self.progress_px:
                self.hab_level = min(self.hab_level + 1, self.give_up)
            else:
                self.hab_level = 0
        self.last_check_x = mario_x
        return self.hab_level < self.give_up

    def reset(self):
        """MDN's fixed-duration backup (SPEC section 2) ends with a clean
        slate for the escape reflex -- backing up is a discrete corrective
        action, not a lingering state."""
        self.last_check_x = None
        self.hab_level = 0
