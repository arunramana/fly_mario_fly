# What this file does, in plain English:
# Fixes the three Phase 3 numbers (pursuit strength, how wide the "straight ahead"
# zone is, and the home-landmark strength) by the rules written in
# docs/SPEC_phase3.md, using only synthetic stimuli: a small dot that sits to the
# left, right or ahead, and a static cue on the right, fed into the real brain.
# It never looks at the game. It also shows the same sweeps on rewired brains.
"""brain/senses_calibrate.py -- docs/SPEC_phase3.md section 3.

    .venv/Scripts/python.exe -m brain.senses_calibrate [--shuffles 5]
    .venv/Scripts/python.exe -m brain.senses_calibrate --arousal      # SPEC section 11: the PURSUIT_AROUSAL default only

Prints the windows and the three values. It does not write them: the values are copied once into brain/calibration.py
(LC10A_GAIN, LC10A_AZIMUTH_SPLIT, GOAL_CUE_SALIENCE) and frozen. If a window is empty the run reports it and stops.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np

from brain import builder
from brain.brain import Brain
from brain.calibration import Calibration
from brain.mechanisms import PursuitMechanism, TargetMechanism, azimuth_shares
from brain.motor_map import MotorMap

GRID = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40)       # per-neuron drive e
SPLIT_CANDIDATES = (10.0, 20.0, 30.0, 45.0, 60.0, 90.0)
AROUSAL_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)   # SPEC section 11
SEEDS = (9400, 9401, 9402, 9403, 9404)
FRAMES, SKIP = 50, 20                                          # hold 50 frames, measure frames 20-49 (steady state)
PRESS_MIN, PRESS_MAX = 0.90, 0.05                              # "pressed on >= 90 %", "pressed on <= 5 %"


@dataclass
class Hold:
    """Fractions of the measured frames for one seed."""
    left: float
    right: float
    b: float
    steer_left: float          # steer < -threshold (the DNa steering rule alone)
    mdn: float                 # MDN above its threshold
    gf: int                    # GF threshold crossings (whole hold)


def hold(brain: Brain, mech: TargetMechanism, drive_left: float, drive_right: float, seed: int, frames: int = FRAMES) -> Hold:
    brain.reset(seed)
    mm, thr = MotorMap(brain.cal.motor), brain.cal.motor
    acc = np.zeros(5)
    gf = 0
    for f in range(frames):
        brain.apply(mech.drive(drive_left, drive_right))
        r = brain.step_frame()
        b = mm.read(r)
        gf += int(r.gf_spiked)
        if f >= SKIP:
            steer = mm._team(r, mm._row["right"], "R") - mm._team(r, mm._row["left"], "L")
            acc += (b.left, b.right, b.b, steer < -thr.steer_threshold, mm._team(r, mm._row["back"]) > thr.back_threshold)
    acc /= frames - SKIP
    return Hold(*acc, gf)


def passes(test: str, holds: list[Hold]) -> bool:
    """SPEC section 3: every seed must satisfy the test's conditions, and the GF must not cross."""
    if any(h.gf for h in holds):
        return False
    if test == "R":
        return all(h.right >= PRESS_MIN and h.left <= PRESS_MAX and h.mdn <= PRESS_MAX for h in holds)
    if test == "L":
        return all(h.steer_left >= PRESS_MIN and h.right <= PRESS_MAX and h.mdn <= PRESS_MAX for h in holds)
    if test == "C":
        return all(h.left <= PRESS_MAX for h in holds)
    if test == "B":
        return all(h.b >= PRESS_MIN for h in holds)
    raise ValueError(test)


def window(ok: dict[float, bool]) -> tuple[float, float] | None:
    """The contiguous run of passing grid values starting at the smallest passing one (None if nothing passes)."""
    vals = sorted(ok)
    start = next((i for i, v in enumerate(vals) if ok[v]), None)
    if start is None:
        return None
    end = start
    while end + 1 < len(vals) and ok[vals[end + 1]]:
        end += 1
    return vals[start], vals[end]


def sig2(x: float) -> float:
    """2 significant figures."""
    return float(f"{x:.2g}")


def sweep(brain: Brain, mech: TargetMechanism, grid=GRID, seeds=SEEDS) -> dict[str, dict[float, bool]]:
    out = {t: {} for t in "RLCB"}
    for e in grid:
        R = [hold(brain, mech, 0.0, e, s) for s in seeds]
        L = [hold(brain, mech, e, 0.0, s) for s in seeds]
        C = [hold(brain, mech, e / 2, e / 2, s) for s in seeds]
        out["R"][e], out["L"][e], out["C"][e], out["B"][e] = passes("R", R), passes("L", L), passes("C", C), passes("B", R)
        m = lambda hs, k: np.mean([getattr(h, k) for h in hs])
        print(f"  e={e:>4}: R {out['R'][e]!s:5} L {out['L'][e]!s:5} C {out['C'][e]!s:5} B {out['B'][e]!s:5} | "
              f"R: right {m(R, 'right'):.2f} left {m(R, 'left'):.2f} b {m(R, 'b'):.2f} mdn {m(R, 'mdn'):.2f} | "
              f"L: steerL {m(L, 'steer_left'):.2f} right {m(L, 'right'):.2f} mdn {m(L, 'mdn'):.2f} | C: left {m(C, 'left'):.2f} | "
              f"gf {sum(h.gf for h in R + L + C)}", flush=True)
    return out


def derive_values(w: dict[str, dict[float, bool]], a_lo: float) -> dict:
    """Rules 1 and 2 of SPEC section 3 from the sweep (a pure function of the sweep: unit-tested on made-up windows)."""
    goal = window({e: w["R"][e] and w["B"][e] for e in w["R"]})
    pursuit = window({e: w["R"][e] and w["L"][e] and w["C"][e] for e in w["R"]})
    out = {"goal_window": goal, "pursuit_window": pursuit, "a_lo": a_lo}
    out["GOAL_CUE_SALIENCE"] = None if goal is None else sig2((goal[0] + goal[1]) / 2)
    if pursuit is not None and pursuit[0] / a_lo < pursuit[1]:
        out["gain_interval"] = (pursuit[0] / a_lo, pursuit[1])
        out["LC10A_GAIN"] = sig2((pursuit[0] / a_lo + pursuit[1]) / 2)
    else:
        out["gain_interval"], out["LC10A_GAIN"] = None, None
    return out


def derive_split(brain: Brain, net, gain: float, a_lo: float, seeds=SEEDS) -> tuple[float | None, dict]:
    """Rule 3: the largest candidate for which az +45 passes R, az -45 passes L and az 0 passes C at a = a_lo and a = 1."""
    detail, best = {}, None
    for split in SPLIT_CANDIDATES:
        mech = PursuitMechanism(net, gain=gain, split_deg=split)
        ok = True
        for a in (a_lo, 1.0):
            for az, test in ((45.0, "R"), (-45.0, "L"), (0.0, "C")):
                l, r = azimuth_shares(az, split)
                k = gain * a
                holds = [hold(brain, mech, k * l, k * r, s) for s in seeds]
                p = passes(test, holds)
                detail[(split, a, az)] = p
                ok &= p
        print(f"  split {split:>4}: {'passes' if ok else 'fails'}", flush=True)
        if ok:
            best = split
    return best, detail


def arousal_ok(brain: Brain, mech: PursuitMechanism, a: float, seeds=SEEDS) -> dict[str, bool]:
    """SPEC section 11: at fly-state arousal `a` a dot at az +45 passes R, az -45 passes L, az 0 passes C, and a static dot
    (no drive: nothing to track) presses nothing and fires no GF."""
    out = {}
    for az, test in ((45.0, "R"), (-45.0, "L"), (0.0, "C")):
        l, r = azimuth_shares(az, mech.split_deg)
        k = mech.gain * a
        out[test] = passes(test, [hold(brain, mech, k * l, k * r, s) for s in seeds])
    idle = [hold(brain, mech, 0.0, 0.0, s) for s in seeds]
    out["static"] = all(h.left <= PRESS_MAX and h.right <= PRESS_MAX and h.b <= PRESS_MAX and h.gf == 0 for h in idle)
    return out


def derive_arousal(ok: dict[float, bool]) -> float | None:
    """The default PURSUIT_AROUSAL: midpoint of the contiguous passing window of the arousal grid, 2 significant figures."""
    w = window(ok)
    return None if w is None else sig2((w[0] + w[1]) / 2)


def arousal_main(shuffles: int) -> None:
    net = builder.load_or_build()
    cal = Calibration.load()
    brain = Brain(net, cal, calibration_hash="senses_calibrate")
    mech = PursuitMechanism(net)
    print(f"network {net.build_hash()}  gain {mech.gain}  split {mech.split_deg}", flush=True)
    ok = {}
    for a in AROUSAL_GRID:
        r = arousal_ok(brain, mech, a)
        ok[a] = all(r.values())
        print(f"  a={a:.1f}: {r} -> {'pass' if ok[a] else 'fail'}", flush=True)
    print(f"window {window(ok)}  RESULT PURSUIT_AROUSAL={derive_arousal(ok)}", flush=True)
    for k in range(1, shuffles + 1):                     # reported only
        twin = Brain(net.shuffled(k, "degree"), cal, calibration_hash="senses_calibrate")
        res = {a: arousal_ok(twin, mech, a, SEEDS[:2]) for a in (0.5, 1.0)}
        print(f"  shuffle {k} (degree): {res}", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffles", type=int, default=5)
    ap.add_argument("--arousal", action="store_true", help="only the PURSUIT_AROUSAL default (SPEC section 11)")
    args = ap.parse_args(argv)
    if args.arousal:
        return arousal_main(args.shuffles)
    net = builder.load_or_build()
    cal = Calibration.load()
    brain = Brain(net, cal, calibration_hash="senses_calibrate")
    mech = TargetMechanism(net)
    a_lo = cal.derivation["rest"]["walk"]["mean"] / cal.motor.walk_threshold
    print(f"network {net.build_hash()}  a_lo (rest DNp09 mean / walk threshold) = {a_lo:.3f}", flush=True)
    w = sweep(brain, mech)
    vals = derive_values(w, a_lo)
    print(vals, flush=True)
    if vals["LC10A_GAIN"] is None or vals["GOAL_CUE_SALIENCE"] is None:
        print("STOP: an empty window (SPEC section 3); nothing is chosen.")
        return
    split, _ = derive_split(brain, net, vals["LC10A_GAIN"], a_lo)
    print(f"LC10A_AZIMUTH_SPLIT = {split}")
    print(f"RESULT GOAL_CUE_SALIENCE={vals['GOAL_CUE_SALIENCE']} LC10A_GAIN={vals['LC10A_GAIN']} LC10A_AZIMUTH_SPLIT={split}", flush=True)
    if split is None:
        print("STOP: no azimuth split candidate passes (SPEC section 3).")
    g = vals["GOAL_CUE_SALIENCE"]
    # reported only: the same cue on rewired brains with the same fixed numbers
    for k in range(1, args.shuffles + 1):
        for mode in ("degree", "class"):
            twin = Brain(net.shuffled(k, mode), cal, calibration_hash="senses_calibrate")
            parts = []
            for name, (l, r) in {"goal cue R": (0.0, g), "cue L": (g, 0.0)}.items():
                h = [hold(twin, mech, l, r, s) for s in SEEDS[:2]]
                m = lambda key: np.mean([getattr(x, key) for x in h])
                parts.append(f"{name}: left {m('left'):.2f} right {m('right'):.2f} b {m('b'):.2f} gf {sum(x.gf for x in h)}")
            print(f"  shuffle {k} ({mode}): " + " | ".join(parts), flush=True)


if __name__ == "__main__":
    main()
