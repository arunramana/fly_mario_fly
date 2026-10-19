"""Headroom: a creature you cannot jump over does not loom as much.

Whole-fly switch. While it is on, the looming sense scales a creature's angle by min(1, rise / (height + clearance)):
rise = how far Mario's head can lift from the ground he took off from before a ceiling stops it, over the span from
him to the creature. Under a low ceiling the Giant Fiber is spared a jump that would only bump his head. (Invented
rule; the factor itself is applied in looming.py, this sense raises the switch and shows the working.)
"""
from __future__ import annotations

from fly_mario.contracts import KnobSpec, SenseOutput
from fly_mario.senses.kit import draw
from fly_mario.senses.kit.geom import feet_of
from fly_mario.senses.kit.headroom import rise_available


class Headroom:
    name = "headroom"
    label = "Headroom (a low ceiling quiets the loom)"
    effect = "Scales a creature's looming angle by how much room there is to jump over it."
    scope = "whole_fly"
    colour = draw.RED
    line = "dotted"
    feeds = ["escape"]
    order = 0                      # before the looming sense, which reads the switch
    knobs = [
        KnobSpec("headroom.clearance", "Clearance wanted over the creature", "none", "generous", 2.0, 0.0, 8.0,
                 origin="invented", evolvable=False),
    ]

    def cue(self, objects, mario, facts, knobs, memory):
        feet = feet_of(mario)
        if not mario.airborne or memory.get("ground") is None:
            memory["ground"] = feet
        rise = rise_available(objects, facts, mario.x, mario.x + mario.w, memory["ground"], mario.h)
        head = memory["ground"] - mario.h
        return SenseOutput(
            overlay=[draw.line_(mario.x, head - rise, mario.x + mario.w, head - rise, draw.RED, "dotted")],
            modifiers={"headroom": 1.0, "headroom_clearance": knobs["headroom.clearance"]},
            steps=[draw.step("rise", "px the head can lift before a ceiling", rise, rise / facts["mario"]["jump_apex"])])


PLUGIN = Headroom()
