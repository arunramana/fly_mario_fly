"""Hearing: a ? block hums, and Johnston's organ (JO) carries the hum straight onto the Giant Fiber.

Invented cue, real wiring: the 20 JO neurons with a direct edge onto the Giant Fiber. The nearest block that Mario
could reach with a full jump (its underside at most `hearing.reach_px` above the floor) and that is not fully
behind him hums at  gain * theta,  theta = the angle the block subtends at his eye. A hum is not noisy (the sensor
noise belongs to the visual and olfactory inputs).
"""
from __future__ import annotations

import numpy as np

from fly_mario.contracts import KnobSpec, SenseOutput
from fly_mario.senses.kit import draw
from fly_mario.senses.kit.geom import eye_of, theta_of
from fly_mario.senses.kit.world import floor_y


class Hearing:
    name = "hearing"
    label = "Hearing (a ? block hums)"
    effect = "The nearest reachable ? block hums into Johnston's organ; loud enough and the Giant Fiber fires: Mario jumps to hit it."
    scope = "per_object"
    colour = draw.GREEN
    line = "solid"
    feeds = ["hearing"]
    order = 30
    raises = []
    reads = []
    LEVEL_NORM = 5.0               # a hum of this size fills the "hum" bar
    knobs = [
        KnobSpec("hearing.gain", "Hum loudness", "quiet", "loud", 14.5342, 13.606, 54.765, scale="log",
                 origin="invented", evolvable=True, floor=13.6057),
        KnobSpec("hearing.reach_px", "Reach", "low blocks only", "high blocks too", 64.0, 16.0, 96.0,
                 origin="invented", evolvable=True),
        KnobSpec("hearing.eye_dy", "Ear height", "at the head", "lower", 0.0, 0.0, 16.0,
                 origin="invented", evolvable=True),
    ]

    def cue(self, objects, mario, facts, knobs, memory):
        floor = floor_y(facts)
        ex, ey = eye_of(mario, knobs["hearing.eye_dy"])
        best = None
        for o in objects:
            b = o.box
            bottom = b.y + b.h
            if floor - bottom > knobs["hearing.reach_px"] or b.x + b.w <= mario.x:
                continue                                    # out of reach, or fully behind him
            d = float(np.hypot(ex - (b.x + b.w / 2), ey - bottom))
            if best is None or d < best[0]:
                best = (d, b, bottom)
        if best is None:
            level, d, theta = 0.0, 0.0, 0.0
            overlay = []
        else:
            d, b, bottom = best
            theta = theta_of(d, b.h)
            level = knobs["hearing.gain"] * theta
            overlay = [draw.box(b.x, b.y, b.w, b.h, draw.GREEN),
                       draw.line_(ex, ey, b.x + b.w / 2, bottom, draw.GREEN, "dotted")]
        steps = [
            draw.step("distance", "eye to the block's underside", d, d / facts["grid"]["screen_w"]),
            draw.step("angle", "theta = 2*atan(h / 2d)", theta, theta / np.pi),
            draw.step("hum", "gain * theta", level, level / self.LEVEL_NORM, "JO"),
        ]
        return SenseOutput(inputs={"JO": level}, overlay=overlay, steps=steps)


PLUGIN = Hearing()
