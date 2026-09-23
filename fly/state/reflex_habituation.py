# What this file does, in plain English:
# Makes a reflex give up when it keeps firing without getting anywhere, as
# a fly's escape reflex does. Each time the reflex wants to fire it checks
# how far Mario has moved forward since the last check; after 3 checks in
# a row with under 16 pixels of progress the reflex is blocked until
# progress resumes or it is reset. Used for the escape jump and climbing.
"""fly/state/reflex_habituation.py -- SPEC_habituation.md section 1. Giant
Fiber pathway habituation, a documented property of the fly's reflex
circuitry, not a timeout. Takes plain x-progress from the caller and never
reads RAM.
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
        # Read the module defaults at construction, not definition, so a
        # later override of HAB_GIVE_UP/HAB_PROGRESS_PX takes effect.
        self.give_up = HAB_GIVE_UP if give_up is None else give_up
        self.progress_px = HAB_PROGRESS_PX if progress_px is None else progress_px

    def check(self, x) -> bool:
        """Call exactly once per frame the reflex's OWN trigger condition
        is true. Returns whether the reflex should actually fire this time
        (False once habituation has reached give_up). `x` is the caller's
        forward position in pixels."""
        if self.last_check_x is not None:
            progress = x - self.last_check_x
            if progress < self.progress_px:
                self.hab_level = min(self.hab_level + 1, self.give_up)
            else:
                self.hab_level = 0
        self.last_check_x = x
        return self.hab_level < self.give_up

    def reset(self):
        """MDN's fixed-duration backup (SPEC section 2) ends with a clean
        slate for the escape reflex -- backing up is a discrete corrective
        action, not a lingering state."""
        self.last_check_x = None
        self.hab_level = 0
