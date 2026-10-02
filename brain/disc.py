# What this file does, in plain English:
# The synthetic test used to calibrate and check the brain without the game: a
# disc that grows the way an approaching object does, fed into the brain only
# through the looming mechanism, plus a no-stimulus test that checks nothing
# switches itself on. It records the angle at which the Giant Fiber first fires.
"""brain/disc.py -- the bridge/loom_disc.py bench (same disc, same frame rate, same angle bookkeeping) for brain.Brain.

theta(t) = 2 atan((l/v) / tau), tau = time to collision, start at 2 deg, one sample per 16.7 ms frame. Inputs are
exactly what the policy supplies: the disc enters through LoomingMechanism -> Brain.apply, nothing else.
"""

from __future__ import annotations

import math

from bridge.loom_disc import FRAME_MS, THETA0_DEG
from brain.brain import Brain, Readout
from brain.mechanisms import LoomingMechanism


def run_disc(brain: Brain, mech: LoomingMechanism, lv_ms: float, seed: int = 0) -> list[dict]:
    """One looming disc. One record per frame: theta (deg), tau (ms), GF membrane/spike, TTMn, the full Readout."""
    tau0 = lv_ms / math.tan(math.radians(THETA0_DEG) / 2.0)
    brain.reset(seed)
    prev, out = 0.0, []
    for f in range(int(tau0 / FRAME_MS) + 3):
        tau = tau0 - f * FRAME_MS
        if tau <= 0:
            break
        th = 2.0 * math.atan(lv_ms / tau)
        dth, prev = th - prev, th
        brain.apply(mech.encode({"L": th, "R": th}, {"L": dth, "R": dth}))
        r = brain.step_frame()
        out.append(dict(tau=tau, theta=math.degrees(th), mem=r.gf_membrane, spike=r.gf_spiked, readout=r,
                        ttmn=max(r.side("TTMn", "L"), r.side("TTMn", "R"))))
    return out


def rest_run(brain: Brain, frames: int = 2000, seed: int = 0) -> list[Readout]:
    """No stimulus, noise only: the Readout of every frame."""
    brain.reset(seed)
    return [brain.step_frame() for _ in range(frames)]


def rest_margin(brain: Brain, frames: int = 2000, seed: int = 0, skip: int = 500) -> dict[str, dict[str, float]]:
    """How close the no-stimulus activity comes to each motor threshold: max rest signal, threshold and their ratio
    (1.0 = touching). A report only; nothing is re-tuned from it. Known risk (SPEC_brain_core.md section 5): on shuffled
    wiring the rest maximum sits within ~8 % (steer) and ~14 % (back) of the thresholds."""
    from brain.calibrate import _motor_signals
    rows = rest_run(brain, frames, seed)[skip:]
    thr = brain.cal.motor
    limits = {"walk": thr.walk_threshold, "steer": thr.steer_threshold, "back": thr.back_threshold}
    return {k: {"max": float(v.max()), "threshold": limits[k], "ratio": float(v.max()) / limits[k]}
            for k, v in _motor_signals(rows).items()}


def first(rec: list[dict], key: str):
    """First record where boolean `key` is true (or None)."""
    return next((r for r in rec if r[key]), None)
