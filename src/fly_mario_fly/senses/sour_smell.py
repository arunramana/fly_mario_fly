"""Sour smell: the nearest live enemy smells of acid; the acid receptors (ORN_DC4) of both antennae drive the
real DC4 -> relay -> moonwalker (MDN) wiring, and the fly backs up.

Invented cue, real wiring. Level = gain * theta (the angle the enemy subtends), the same for both antennae, with
sensor noise. Like a loom candidate, the enemy must not be behind Mario's left edge and must not have been got past
in this jump ("cleared"); a Koopa in its shell does not smell.

REAR (sour_smell.rear, a switch): when on, the nearest sour enemy on EITHER side counts, and a source behind Mario
drives DC4 -> MDN like one ahead. Off (the default) only a source ahead smells.
"""
from __future__ import annotations

import numpy as np

from fly_mario_fly.contracts import KnobSpec, SenseOutput
from fly_mario_fly.senses.kit import draw
from fly_mario_fly.senses.kit.geom import gap, identity, is_behind, is_cleared, over, theta_of


class SourSmell:
    name = "sour_smell"
    label = "Sour smell (an enemy smells of acid)"
    effect = "The nearest enemy drives the acid receptors; strong enough and the moonwalker neurons fire: Mario backs up."
    scope = "per_object"
    colour = draw.YELLOW
    line = "dotted"
    feeds = ["aversion"]
    order = 20
    knobs = [
        KnobSpec("sour_smell.gain", "Sourness", "faint", "strong", 8.0587, 4.3305, 32.235, scale="log",
                 origin="invented", evolvable=True, floor=4.3305),
        KnobSpec("sour_smell.rear", "Smells behind too", "ahead only", "either side", 0.0, 0.0, 1.0,
                 origin="invented", evolvable=False, kind="switch"),
    ]
    raises = []
    reads = []
    LEVEL_NORM = 5.0               # a drive of this size fills the "sourness" bar

    def cue(self, objects, mario, facts, knobs, memory):
        cleared = memory.setdefault("cleared", set())
        if not mario.airborne:
            cleared.clear()
        else:
            cleared |= {identity(o) for o in objects if is_cleared(mario, o.box.y, o.box.x, o.box.x + o.box.w)}
        rear_on = knobs["sour_smell.rear"] >= 0.5
        best = None
        for o in sorted(objects, key=lambda o: o.state.get("slot", o.id)):
            b = o.box
            if o.state.get("shell") or identity(o) in cleared or is_cleared(mario, b.y, b.x, b.x + b.w):
                continue
            rear = False
            if not (b.x >= mario.x or over(mario, b.x, b.x + b.w)):
                if not (rear_on and is_behind(mario, b.x, b.w)):
                    continue
                rear = True
            d = gap(mario, b.x, b.y, b.w, b.h, rear=rear)
            if best is None or d < best[0]:
                best = (d, b, rear)
        level, theta, d = 0.0, 0.0, 0.0
        overlay = []
        if best is not None:
            d, b, rear = best
            theta = theta_of(d, b.h)
            level = knobs["sour_smell.gain"] * theta * memory.noise()
            overlay = [draw.box(b.x - 4, b.y - 4, b.w + 8, b.h + 8, draw.YELLOW, "dotted")]
        steps = [
            draw.step("distance", "gap = hypot(gap_x, gap_y)", d, d / facts["grid"]["screen_w"]),
            draw.step("angle", "theta = 2*atan(h / 2d)", theta, theta / np.pi),
            draw.step("sourness", "gain * theta", level, level / self.LEVEL_NORM, "DC4_L"),
        ]
        return SenseOutput(inputs={"DC4_L": level, "DC4_R": level}, overlay=overlay, steps=steps)


PLUGIN = SourSmell()
