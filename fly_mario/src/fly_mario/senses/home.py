"""Home: a constant pull to keep walking right.

The direction of travel is ours, not the fly's: a steady drive into the right-eye target tracker (LC10a_R), which
the real wiring turns into forward walking (DNp09) and steering (DNa). Whole-fly: it is not about any object.
"""
from __future__ import annotations

from fly_mario.contracts import KnobSpec, OverlayItem, SenseOutput
from fly_mario.senses.kit import draw


class Home:
    name = "home"
    label = "Home (keep going right)"
    effect = "A steady drive into the right-eye target tracker: the fly walks right and steers right."
    scope = "whole_fly"
    colour = draw.WHITE
    line = "solid"
    feeds = ["walking"]
    order = 60
    knobs = [
        KnobSpec("home.drive", "Pull to the right", "weak", "strong", 0.5, 0.1134, 1.8142, scale="log",
                 origin="invented", evolvable=True, floor=0.1003),
    ]

    def cue(self, objects, mario, facts, knobs, memory):
        drive = knobs["home.drive"]
        return SenseOutput(
            inputs={"LC10a_R": drive},
            overlay=[OverlayItem("dot", {"anchor": "screen_right", "y": mario.y}, draw.WHITE)],   # a marker on the right edge, at eye height
            steps=[draw.step("home", "constant drive into LC10a_R", drive, drive / 2.0, "LC10a_R")])


PLUGIN = Home()
