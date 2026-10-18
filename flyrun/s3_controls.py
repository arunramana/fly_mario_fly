"""Part S3 controls: identical senses v2 + motor rules, only the 'brain' differs.
ThetaRuleV2: no brain. Right always; press A when grounded and the chosen threat's (noisy) theta >= TRIGGER, hold while theta >= TRIGGER,
release when it fades, same landing reset (A up exactly one frame on airborne -> grounded) as Muscle2.
BlindTimer: no senses. Right always, A held 30 frames then up 10 (every 40)."""
import numpy as np

from . import env as E
from .motor import Muscle2

TIMER_HOLD, TIMER_PERIOD = 30, 40      # INVENTED (fixed): the blind timer's cadence (S3 spec)


class ThetaRuleV2:
    trigger_deg = 43.6                 # set from the measured trigger angle by the harness (class attribute on a subclass)

    def __init__(self, knobs, rng):
        self.m = Muscle2()
        self.thr = np.radians(self.trigger_deg)
        self.airborne = False

    def act(self, loom):
        th = loom.theta_noisy
        a = self.m.step(th, self.thr, self.thr, self.airborne)      # theta plays TTMn: same press / hold / release / landing reset
        return E.RIGHT_A if a else E.RIGHT


class BlindTimer:
    def __init__(self, knobs, rng):
        self.t = 0

    def act(self, loom):
        a = self.t % TIMER_PERIOD < TIMER_HOLD
        self.t += 1
        return E.RIGHT_A if a else E.RIGHT


def theta_rule(trigger_deg):
    return type("ThetaRuleV2Measured", (ThetaRuleV2,), {"trigger_deg": float(trigger_deg)})
