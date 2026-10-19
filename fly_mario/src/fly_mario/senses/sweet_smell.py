"""Sweet smell: the nearest attractive thing (a mushroom) drives the attractive odour receptors (ORN) of the antenna
on its side, and the real ORN -> relay -> DNa wiring steers the fly toward it.

Invented cue, real wiring. Level = gain * theta (the angle the object subtends at Mario's eye), into the left
antenna if the object's centre is left of Mario's centre, else the right. The smell carries sensor noise.
"""
from __future__ import annotations

import numpy as np

from fly_mario.contracts import KnobSpec, SenseOutput
from fly_mario.senses.kit import draw
from fly_mario.senses.kit.geom import eye_of, theta_of


class SweetSmell:
    name = "sweet_smell"
    label = "Sweet smell (a mushroom smells good)"
    effect = "The nearest sweet object drives the antenna on its side, which steers the fly toward it."
    scope = "per_object"
    colour = draw.GREEN
    line = "solid"
    feeds = ["attraction"]
    order = 40
    knobs = [
        KnobSpec("sweet_smell.gain", "Smell strength", "faint", "strong", 213.9495, 109.86, 1757.7, scale="log",
                 origin="invented", evolvable=True, floor=6.452),
        KnobSpec("sweet_smell.eye_dy", "Nose height", "at the head", "lower", 0.0, 0.0, 16.0,
                 origin="invented", evolvable=True),
    ]

    def cue(self, objects, mario, facts, knobs, memory):
        ex, ey = eye_of(mario, knobs["sweet_smell.eye_dy"])
        best = None
        for o in objects:
            b = o.box
            cx, cy = b.x + b.w / 2, b.y + b.h / 2
            d = float(np.hypot(ex - cx, ey - cy))
            if best is None or d < best[0]:
                best = (d, b, cx)
        left = right = theta = 0.0
        d = 0.0
        overlay = []
        if best is not None:
            d, b, cx = best
            theta = theta_of(d, b.h)
            level = knobs["sweet_smell.gain"] * theta * memory.noise()
            if cx < mario.x + mario.w / 2:                      # left of his centre -> the left antenna
                left = level
            else:
                right = level
            overlay = [draw.box(b.x, b.y, b.w, b.h, draw.GREEN)]
        steps = [
            draw.step("distance", "eye to the object's centre", d, d / 256.0),
            draw.step("angle", "theta = 2*atan(h / 2d)", theta, theta / np.pi),
            draw.step("left antenna", "gain * theta (object on the left)", left, left / 200.0, "ORN_L"),
            draw.step("right antenna", "gain * theta (object on the right)", right, right / 200.0, "ORN_R"),
        ]
        return SenseOutput(inputs={"ORN_L": left, "ORN_R": right}, overlay=overlay, steps=steps)


PLUGIN = SweetSmell()
