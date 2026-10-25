"""A sense built from a fixed recipe, so a new one can be declared with numbers and names instead of code.

The MCP server (`add_sense`) writes a plug-in file that only calls `CueSense(...)` with validated literals. Same contract as every
hand-written sense: `cue(objects, mario, facts, knobs, memory) -> SenseOutput`; same honesty rule: the cue is invented (orange),
the groups it drives are real input neurons on a declared route (teal).

Cue recipes (a closed list):
  angular_size  the nearest attached object's visual angle theta = 2*atan(h / 2d) from Mario's eye, times the strength dial and
                the run's sensor noise. With `split_by_side` and two groups ending _L / _R, only the antenna on the object's side
                gets it (as sweet_smell does).
  proximity     strength * (1 - d / range_px) for the nearest object within range_px of Mario's eye, else 0. Noisy like the others.
  constant      the strength dial, every frame, whatever the objects are (whole-fly scope).
"""
from __future__ import annotations

import numpy as np

from fly_mario_fly.contracts import KnobSpec, SenseOutput
from fly_mario_fly.senses.kit import draw
from fly_mario_fly.senses.kit.geom import eye_of, theta_of

CUES = ("angular_size", "proximity", "constant")
COLOURS = {"red": draw.RED, "green": draw.GREEN, "yellow": draw.YELLOW, "white": draw.WHITE}


class CueSense:
    line = "solid"
    raises: list = []
    reads: list = []

    def __init__(self, *, name, label, effect, cue, feeds, drives, gain, colour="green", range_px=96.0,
                 split_by_side=False, order=50):
        if cue not in CUES:
            raise ValueError(f"unknown cue {cue!r}; known: {list(CUES)}")
        self.name, self.label, self.effect, self.cue_kind = name, label, effect, cue
        self.feeds, self.drives = list(feeds), tuple(drives)
        self.scope = "whole_fly" if cue == "constant" else "per_object"
        self.colour = COLOURS[colour]
        self.range_px, self.split_by_side, self.order = float(range_px), bool(split_by_side), int(order)
        self.gain_key = f"{name}.gain"
        self.knobs = [KnobSpec(self.gain_key, "Strength", "faint", "strong", float(gain), float(gain) / 8.0, float(gain) * 8.0,
                               scale="log", origin="invented", evolvable=True)]
        self.LEVEL_NORM = float(gain) * np.pi        # a level of this size fills the bar

    def _levels(self, level: float, side: str) -> dict:
        if self.split_by_side and len(self.drives) == 2:
            left = [g for g in self.drives if g.endswith("_L")]
            right = [g for g in self.drives if g.endswith("_R")]
            if left and right:
                return {left[0]: level if side == "L" else 0.0, right[0]: level if side == "R" else 0.0}
        return {g: level for g in self.drives}

    def cue(self, objects, mario, facts, knobs, memory):
        gain = knobs[self.gain_key]
        if self.cue_kind == "constant":
            ins = {g: gain for g in self.drives}
            return SenseOutput(inputs=ins, steps=[draw.step(self.name, "constant drive", gain, gain / self.LEVEL_NORM, g)
                                                  for g in self.drives])
        ex, ey = eye_of(mario, 0.0)
        best = None
        for o in objects:
            b = o.box
            cx, cy = b.x + b.w / 2, b.y + b.h / 2
            d = float(np.hypot(ex - cx, ey - cy))
            if best is None or d < best[0]:
                best = (d, b, cx)
        if best is None:
            return SenseOutput(inputs={g: 0.0 for g in self.drives},
                               steps=[draw.step("object", "nothing attached in view", 0.0, 0.0)])
        d, b, cx = best
        if self.cue_kind == "angular_size":
            theta = theta_of(d, b.h)
            raw, formula = gain * theta, "gain * theta, theta = 2*atan(h / 2d)"
        else:
            raw = gain * max(0.0, 1.0 - d / self.range_px)
            formula = f"gain * (1 - d / {self.range_px:g})"
        level = raw * memory.noise()
        side = "L" if cx < mario.x + mario.w / 2 else "R"
        ins = self._levels(level, side)
        steps = [draw.step("distance", "eye to the object's centre", d, d / facts["grid"]["screen_w"]),
                 draw.step("level", formula, level, level / self.LEVEL_NORM)]
        steps += [draw.step(g, "drive into this group", v, v / self.LEVEL_NORM, g) for g, v in ins.items()]
        return SenseOutput(inputs=ins, overlay=[draw.box(b.x, b.y, b.w, b.h, self.colour)], steps=steps)
