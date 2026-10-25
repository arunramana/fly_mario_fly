"""Rear eye: an enemy coming up from BEHIND can loom too.

Whole-fly switch. While it is on, the looming sense lets an enemy behind Mario compete for the detectors, but only
while its gap is shrinking (an object that recedes contracts on the retina; it does not loom). Faces and pits stay
ahead-only. The tracking lives in looming.py; this sense raises the switch and counts what is behind.
"""
from __future__ import annotations

from fly_mario_fly.contracts import SenseOutput
from fly_mario_fly.senses.kit import draw
from fly_mario_fly.senses.kit.geom import is_behind
from fly_mario_fly.senses.kit.world import kind_of
from fly_mario_fly.rules import Route, declare


class RearEye:
    name = "rear_eye"
    label = "Rear eye (looming from behind)"
    effect = "An enemy closing in from behind can drive the looming detectors."
    scope = "whole_fly"
    colour = draw.RED
    line = "dotted"
    feeds = ["escape"]
    order = 0
    raises = ["rear_eye"]
    reads = []
    BEHIND_NORM = 5.0              # this many enemies behind fill the "behind" bar
    knobs = []

    def cue(self, objects, mario, facts, knobs, memory):
        behind = sum(1 for o in objects if kind_of(o.type) == "enemy" and is_behind(mario, o.box.x, o.box.w))
        overlay = [draw.box(o.box.x, o.box.y, o.box.w, o.box.h, draw.RED, "dotted")
                   for o in objects if kind_of(o.type) == "enemy" and is_behind(mario, o.box.x, o.box.w)]
        return SenseOutput(overlay=overlay, modifiers={"rear_eye": 1.0},
                           steps=[draw.step("behind", "enemies fully behind his left edge", behind, behind / self.BEHIND_NORM)])


PLUGIN = RearEye()


DECLARATION = declare(
    "sense", "invented",
    "Invented modulator: lets an enemy behind Mario compete in the looming cue while it closes in. It drives no neuron itself.",
    route=Route("escape", ("LC4", "LPLC2"), "widens the cue that drives LC4/LPLC2 -> DNp01 -> TTMn"),
    modulates=("rear_eye",))
