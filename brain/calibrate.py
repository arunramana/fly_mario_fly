# What this file does, in plain English:
# Works out the brain's derived numbers from synthetic tests only, never from
# game runs: the one recurrent gain (from the stability criterion), the Giant
# Fiber's firing threshold (so it fires at about 40 degrees, as measured in real
# flies), and the motor-reading thresholds (above what the brain does at rest,
# and below what it does on the calibration discs). It writes brain/calibration.json
# and prints the disc results for the real wiring next to shuffled wiring.
"""brain/calibrate.py -- docs/SPEC_brain_core.md section 5.

    python -m brain.calibrate [--shuffles 5] [--no-write]

Derivations (all on the synthetic disc, l/v 20/40/80 ms, or on a no-stimulus rest run):
  g              = min(G_NOMINAL, STABILITY_MARGIN / rho(W))
  gf_threshold   = mean over the calibration discs of the GF membrane at THETA_GF_DEG (spiking disabled)
  walk/steer/back thresholds = rest mean + REST_Z * rest std of the pooled activity
  a_threshold    = A_FRACTION * the weakest calibration disc's peak A-muscle drive
"""

from __future__ import annotations

import argparse
import dataclasses

import numpy as np

from brain import builder
from brain.brain import Brain
from brain.calibration import (A_FRACTION, CALIBRATION_FILE, CALIBRATION_LV_MS, G_NOMINAL, MOTOR_FLOOR_HZ, MUSCLE_DECAY,
                               REST_Z, STABILITY_MARGIN, THETA_GF_DEG, Calibration, MotorThresholds)
from brain.disc import first, rest_margin, rest_run, run_disc
from brain.mechanisms import LoomingMechanism
from brain.motor_map import MotorMap
from bridge.loom_disc import LV_MS

HUGE = 1e9


def at_theta(rec: list[dict], key: str, theta_deg: float) -> float:
    """`key` interpolated at angular size theta (records are ordered by increasing theta)."""
    th = np.array([r["theta"] for r in rec])
    return float(np.interp(theta_deg, th, [r[key] for r in rec]))


def _motor_signals(rows) -> dict[str, np.ndarray]:
    """Per-frame pooled quantities the motor map thresholds act on."""
    m = MotorMap(MotorThresholds(MUSCLE_DECAY, HUGE, HUGE, HUGE, HUGE))
    walk = np.array([m._team(r, m._row["walk"]) for r in rows])
    back = np.array([m._team(r, m._row["back"]) for r in rows])
    steer = np.array([m._team(r, m._row["right"], "R") - m._team(r, m._row["left"], "L") for r in rows])
    return {"walk": walk, "back": back, "steer": np.abs(steer)}


def muscle_trace(rec: list[dict]) -> np.ndarray:
    m = MotorMap(MotorThresholds(MUSCLE_DECAY, HUGE, HUGE, HUGE, HUGE))
    return np.array([m.muscle(r["ttmn"]) for r in rec])


def derive(net: builder.BuiltNetwork, rest_frames: int = 2000, rest_seeds=(0, 1)) -> Calibration:
    rho = builder.spectral_radius(net.W, 1.0)
    g = min(G_NOMINAL, STABILITY_MARGIN / rho)
    print(f"rho(W) = {rho:.4f}  ->  g = {g:.4f}")
    stub = Calibration(net.build_hash(), rho, g, HUGE, MotorThresholds(MUSCLE_DECAY, HUGE, HUGE, HUGE, HUGE))
    brain = Brain(net, stub, calibration_hash="derivation")
    mech = LoomingMechanism(net)

    mem = {lv: at_theta(run_disc(brain, mech, lv), "mem", THETA_GF_DEG) for lv in CALIBRATION_LV_MS}
    gf = float(np.mean(list(mem.values())))
    print(f"GF membrane at {THETA_GF_DEG:.0f} deg: {({k: round(v, 5) for k, v in mem.items()})} -> gf_threshold {gf:.5f}")

    # Rest run with the spiking GF in place: what the motor map must stay silent for.
    with_gf = dataclasses.replace(stub, gf_threshold=gf)
    brain = Brain(net, with_gf, calibration_hash="derivation")
    rows = [r for s in rest_seeds for r in rest_run(brain, rest_frames, s)[rest_frames // 4:]]
    sig = _motor_signals(rows)
    thr = {k: max(MOTOR_FLOOR_HZ, float(v.mean() + REST_Z * v.std())) for k, v in sig.items()}
    print("rest (frames %d, seeds %s): " % (len(rows), list(rest_seeds)) +
          " ".join(f"{k} mean {v.mean():.5f} std {v.std():.5f} max {v.max():.5f} -> thr {thr[k]:.5f}" for k, v in sig.items()))

    peaks = {}
    for lv in CALIBRATION_LV_MS:
        peaks[lv] = float(muscle_trace(run_disc(brain, mech, lv)).max())
    a_thr = A_FRACTION * min(peaks.values())
    print(f"peak A-muscle drive per disc {({k: round(v, 3) for k, v in peaks.items()})} -> a_threshold {a_thr:.4f}")

    motor = MotorThresholds(MUSCLE_DECAY, a_thr, thr["walk"], thr["steer"], thr["back"])
    return dataclasses.replace(
        with_gf, motor=motor,
        derivation={"gf_membrane_at_theta": {str(k): v for k, v in mem.items()},
                    "rest": {k: {"mean": float(v.mean()), "std": float(v.std()), "max": float(v.max())} for k, v in sig.items()},
                    "peak_muscle_drive": {str(k): v for k, v in peaks.items()}, "theta_gf_deg": THETA_GF_DEG})


def fire(rec: list[dict]) -> str:
    r = first(rec, "spike")
    return "no fire" if r is None else f"{r['theta']:5.1f} deg ({r['tau']:4.0f} ms before)"


def report(label: str, net: builder.BuiltNetwork, cal: Calibration) -> dict:
    """Disc and rest results for `net` with `cal`'s fixed numbers (unchanged for shuffled twins)."""
    brain = Brain(net, cal, calibration_hash="report")
    mech = LoomingMechanism(net)
    rest = rest_run(brain, 2000, 0)[500:]
    rest_gf = sum(r.gf_spiked for r in rest)
    sig = _motor_signals(rest)
    fires = {}
    print(f"== {label}  (neurons {net.n_neurons}, edges {net.n_edges}, g {cal.g:.3f})")
    print(f"   rest: GF spikes {rest_gf}; max walk {sig['walk'].max():.4f} steer {sig['steer'].max():.4f} back {sig['back'].max():.4f}; "
          f"max TTMn {max(max(r.side('TTMn', 'L'), r.side('TTMn', 'R')) for r in rest):.4f}")
    margins = rest_margin(brain, 2000, 0)
    print("   rest max / threshold: " + " ".join(f"{k} {m['ratio']:.2f}" for k, m in margins.items()) + "  (report only)")
    for lv in LV_MS:
        rec = run_disc(brain, mech, lv)
        f = first(rec, "spike")
        fires[lv] = None if f is None else f["theta"]
        print(f"   l/v {lv:2d} ms: GF {fire(rec):28s} | peak TTMn {max(r['ttmn'] for r in rec):6.2f}")
    return fires


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffles", type=int, default=5)
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()
    net = builder.load_or_build()
    print(f"network {net.build_hash()}: {net.n_neurons} neurons, {net.n_edges} edges")
    cal = derive(net)
    if not args.no_write:
        cal.save()
        print(f"wrote {CALIBRATION_FILE} (hash {Calibration.file_hash()})")
    report("REAL connectome", net, cal)
    for k in range(1, args.shuffles + 1):
        report(f"SHUFFLED {k} (same fixed numbers)", net.shuffled(k), cal)


if __name__ == "__main__":
    main()
