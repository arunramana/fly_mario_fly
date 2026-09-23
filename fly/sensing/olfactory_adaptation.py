"""fly/sensing/olfactory_adaptation.py -- ORN adaptation, moved verbatim
from run_steering.py (REFACTOR_PLAN.md phase 2: "Put RetinotopicMap in
fly/sensing/, where it always belonged" -- this is the same kind of thing,
a sensory-receptor-physiology transform that takes a concentration and
returns a concentration, with no RAM access and no mario dependency).

A real olfactory receptor neuron's response to a SUSTAINED concentration
decays over ~1-2 seconds and recovers once the stimulus is gone -- this is
receptor physiology, not a steering rule, so it lives entirely in the
sensory layer; the WTA code in run_steering.py never needs to know it
exists. ALPHA_ADAPT=1/90 gives a ~1.5s time constant at 60fps -- this runs
once per EMULATOR frame, same cadence as the odour reading itself, so 90
FRAMES really is ~1.5s of wall-clock game time. Unchanged from sprint 009.
"""

from __future__ import annotations

ALPHA_ADAPT = 1.0 / 90.0


class OlfactoryAdaptation:
    """Sensory-layer ORN adaptation, one instance's worth of receptor state
    per hemisphere (L/R match the same split the odour sources already
    route by). Modeled divisively, not subtractively -- a real firing rate
    (or here, a concentration) can't be driven negative by adaptation, it
    can only be divided down towards zero -- as a slow trace `a` of the RAW
    concentration each side has actually been receiving:

        a(t+1) = (1 - ALPHA_ADAPT) * a(t) + ALPHA_ADAPT * raw(t)
        adapted(t) = raw(t) / (1 + a(t))

    Applied to the ODOUR_GAIN/hunger-scaled signal (see ALPHA_ADAPT's
    comment for why) -- `raw` here is that scaled value, not the bare
    1/distance concentration. A source Mario is stuck next to keeps `raw`
    constant, so `a` climbs toward that same value and `adapted` decays
    toward `raw/(1+raw)` -- e.g. a hungry Mario's scaled odour of 2.0
    (comfortably beating HOME_BIAS=1.0) decays toward 2.0/3.0=0.667, which
    loses to HOME_BIAS -- home wins the WTA back even though the raw
    stimulus never went away. Leaving the source (raw -> 0) lets `a` relax
    back down at the same ALPHA_ADAPT rate, and the next encounter starts
    fresh."""

    def __init__(self, alpha: float = ALPHA_ADAPT):
        self.alpha = alpha
        self.a = {"L": 0.0, "R": 0.0}

    def apply(self, raw: dict) -> dict:
        out = {}
        for side in ("L", "R"):
            self.a[side] = (1.0 - self.alpha) * self.a[side] + self.alpha * raw[side]
            out[side] = raw[side] / (1.0 + self.a[side])
        return out
