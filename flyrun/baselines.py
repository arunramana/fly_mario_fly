"""No-brain baseline policies, for fitness comparisons. Each is a factory(knobs, rng) -> object
with act(loom) -> action index. All four use the same emulator, seeds and episode rules as the fly."""
import numpy as np

from . import env as E
from .knobs import RANDOM_A_P, SPAM_FIXED_COOLDOWN, SPAM_FIXED_HOLD
from .motor import Muscle


class Stand:
    def __init__(self, knobs, rng):
        pass

    def act(self, loom):
        return E.NOOP


class AlwaysRight:
    def __init__(self, knobs, rng):
        pass

    def act(self, loom):
        return E.RIGHT


class RightRandomA:
    P_A = RANDOM_A_P   # INVENTED (fixed): per-frame probability of pressing A (seeded, no hold)

    def __init__(self, knobs, rng):
        self.rng = rng

    def act(self, loom):
        return E.RIGHT_A if self.rng.random() < self.P_A else E.RIGHT


class ThetaRule:
    """Right always; A when the combined theta >= THETA_RULE_DEG, same hold/cooldown. No brain."""

    def __init__(self, knobs, rng):
        self.k, self.muscle = knobs, Muscle()
        self.thresh = np.radians(knobs.THETA_RULE_DEG)

    def act(self, loom):
        return E.RIGHT_A if self.muscle.press(loom.theta_noisy >= self.thresh, self.k) else E.RIGHT


class Spam:
    """A timer, no sensing: Right always, A held A_HOLD frames then COOLDOWN frames off, forever."""

    def __init__(self, knobs, rng):
        self.k, self.muscle = knobs, Muscle()

    def act(self, loom):
        return E.RIGHT_A if self.muscle.press(True, self.k) else E.RIGHT


class SpamFixed(Spam):
    """spam_fixed: hold SPAM_FIXED_HOLD (18) + cooldown SPAM_FIXED_COOLDOWN (3) regardless of the knobs (the Part 4 fly's cadence)."""

    def __init__(self, knobs, rng):
        from dataclasses import replace
        super().__init__(replace(knobs, A_HOLD=SPAM_FIXED_HOLD, COOLDOWN=SPAM_FIXED_COOLDOWN), rng)


CONTROLLERS = {"spam": Spam, "spam_fixed": SpamFixed, "stand": Stand, "right": AlwaysRight, "right_randA": RightRandomA,
               "theta_rule": ThetaRule}   # "fly" = controller None
