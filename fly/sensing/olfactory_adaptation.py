"""fly/sensing/olfactory_adaptation.py -- ORN adaptation.

A real olfactory receptor neuron's response to a sustained concentration
decays over ~1-2 seconds and recovers once the stimulus is gone. That is
receptor physiology, not a steering rule, so it lives in the sensory layer
and the steering WTA never sees it. It runs once per emulator frame, so
ALPHA_ADAPT=1/90 is a ~1.5s time constant at 60fps.
"""

from __future__ import annotations

ALPHA_ADAPT = 1.0 / 90.0


class OlfactoryAdaptation:
    """Per-hemisphere receptor state. Divisive, not subtractive, since
    adaptation can divide a rate toward zero but never drive it negative:

        a(t+1) = (1 - ALPHA_ADAPT) * a(t) + ALPHA_ADAPT * raw(t)
        adapted(t) = raw(t) / (1 + a(t))

    `raw` is the gain- and hunger-scaled signal: adapting the bare ~0.04
    concentration would barely move it. Next to a constant source,
    `adapted` decays toward raw/(1+raw) -- a hungry Mario's 2.0 falls to
    0.667 and loses to HOME_BIAS=1.0, so home wins back even though the
    stimulus never left. Moving away lets `a` relax at the same rate."""

    def __init__(self, alpha: float = ALPHA_ADAPT):
        self.alpha = alpha
        self.a = {"L": 0.0, "R": 0.0}

    def apply(self, raw: dict) -> dict:
        out = {}
        for side in ("L", "R"):
            self.a[side] = (1.0 - self.alpha) * self.a[side] + self.alpha * raw[side]
            out[side] = raw[side] / (1.0 + self.a[side])
        return out
