# What this file does, in plain English:
# Turns the activity of the fly's output neurons into game buttons, by a fixed
# table: jump-muscle neuron -> A, walking neuron -> go right and run, steering
# neurons -> left or right, backward-walking neuron -> back up. It only reads
# the brain; it never feeds anything back. Down and Up have no neuron and are
# never pressed. The thresholds come from synthetic tests, not from game runs.
"""brain/motor_map.py -- docs/SPEC_brain_core.md section 7.

Read-only: `read()` takes a Readout and returns buttons. There is no path from here into the brain. The one piece of
state is the A "muscle": a leaky integral of the TTMn onset (a muscle low-passes its motor neuron, and a saturated
TTMn pool stays high long after the twitch), like bridge/controller_modules.MotorDirectModule without its game hooks.
"""

from __future__ import annotations

from dataclasses import dataclass

from brain.brain import Readout
from brain.calibration import MotorThresholds
from brain.manifest import MOTOR_TABLE, UNASSIGNED_BUTTONS, MotorRow


@dataclass(frozen=True)
class Buttons:
    a: bool = False
    b: bool = False
    right: bool = False
    left: bool = False
    down: bool = False      # never pressed: no justified neuron (D4)
    up: bool = False


class MotorMap:
    def __init__(self, thresholds: MotorThresholds, table: tuple[MotorRow, ...] = MOTOR_TABLE):
        self.thr = thresholds
        self._row = {r.button: r for r in table}
        self.reset()

    def reset(self) -> None:
        self.drive = 0.0          # A muscle drive
        self._prev_ttmn = 0.0

    @staticmethod
    def _team(r: Readout, row: MotorRow, side: str | None = None) -> float:
        """Mean activity of the row's populations (one side if given)."""
        vals = [r.side(p, s) for p in row.populations for s in ((side,) if side else ("L", "R"))]
        return sum(vals) / len(vals)

    def muscle(self, ttmn: float) -> float:
        """Advance the A muscle one frame: leaky integral of the TTMn rise (onsets, not sustained level)."""
        rise = max(0.0, ttmn - self._prev_ttmn)
        self._prev_ttmn = ttmn
        self.drive = self.drive * self.thr.muscle_decay + rise
        if self.drive < 1e-12:
            self.drive = 0.0
        return self.drive

    def read(self, r: Readout) -> Buttons:
        a_row = self._row["A"]
        ttmn = max(r.side(p, s) for p in a_row.populations for s in ("L", "R"))
        a = self.muscle(ttmn) >= self.thr.a_threshold
        walk = self._team(r, self._row["walk"]) > self.thr.walk_threshold
        steer = (self._team(r, self._row["right"], "R") - self._team(r, self._row["left"], "L"))
        back = self._team(r, self._row["back"]) > self.thr.back_threshold
        left = back or steer < -self.thr.steer_threshold
        right = (walk or steer > self.thr.steer_threshold) and not left
        return Buttons(a=a, b=walk, right=right, left=left)


assert set(UNASSIGNED_BUTTONS) == {"down", "up"}
