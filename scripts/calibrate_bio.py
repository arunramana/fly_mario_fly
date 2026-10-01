# What this file does, in plain English:
# Works out the calibrated numbers for the "honest fly" mode from the looming-disc test and
# nothing else -- never from game runs. It fixes the Giant Fiber threshold and the second
# escape neuron's threshold from the real circuit, measures how much the firing-rate units
# change scales the jump and wing muscle neurons, and then shows how the real circuit and
# shuffled ones respond with those numbers unchanged.
"""scripts/calibrate_bio.py -- docs/SPEC_bio_calibration.md.

    .venv/Scripts/python.exe -m scripts.calibrate_bio [--shuffles 5]

Derivations (all on the synthetic disc, l/v 10-80 ms):
  stability : g = min(g, margin / rho(W)) per circuit (FullPolicy._g)
  GF        : gf_threshold = mean over l/v 20,40,80 of the DNp01 spike-cell membrane at theta = 55 deg (real circuit)
  DNp02     : dnp02_threshold = DNp02 membrane at theta = 55 deg for l/v 10
  units     : ttmn/dlmn_unit_factor = peak response at clip 200/spike 60 over clip 50/spike 50, same disc and circuit
"""

from __future__ import annotations

import argparse
import dataclasses

import numpy as np

import setuptools  # noqa: F401
from bridge.full_policy import FullPolicy
from bridge.loom_disc import FRAME_MS, LV_MS, first, rest_test, run_disc
from config.params import BioStrictParams, ModulesConfig, MotorDirectParams
from config.project_config import ProjectConfig

THETA_GF_DEG = 55.0      # target angular size (von Reyn et al. 2014; medium-low confidence, to be verified)
HUGE = 1e9


def make(bio: BioStrictParams | None = None, shuffle: int | None = None) -> FullPolicy:
    cfg = ProjectConfig(bio_strict=True, modules=ModulesConfig(motor_direct=MotorDirectParams()))
    if bio is not None:
        cfg = dataclasses.replace(cfg, bio=bio)
    p = FullPolicy(config=cfg, level="1-1", shuffle_seed=shuffle)
    p.reset(0)
    return p


def at_theta(rec: list[dict], key: str, theta_deg: float) -> float:
    """`key` interpolated at angular size theta (records are ordered by increasing theta)."""
    th = np.array([r["theta"] for r in rec])
    return float(np.interp(theta_deg, th, [r[key] for r in rec]))


def fire(rec: list[dict], key: str) -> str:
    r = first(rec, key)
    return "no fire" if r is None else f"{r['theta']:5.1f} deg ({r['tau']:4.0f} ms before)"


def derive(bio: BioStrictParams) -> tuple[float, float, float]:
    """(gf_threshold, dnp02_threshold, dnp02_input_gain) from the real circuit with spiking disabled."""
    p = make(dataclasses.replace(bio, gf_threshold=HUGE, dnp02_threshold=HUGE, dnp02_input_gain=1.0))
    m = {lv: at_theta(run_disc(p, lv), "mem", THETA_GF_DEG) for lv in (20, 40, 80)}
    print("DNp01 membrane at theta = %.0f deg: %s" % (THETA_GF_DEG, {k: round(v, 4) for k, v in m.items()}))
    gf = float(np.mean(list(m.values())))
    m2 = at_theta(run_disc(p, 10), "mem2", THETA_GF_DEG)
    print("DNp02 membrane at theta = %.0f deg, l/v 10 (gain 1): %.5f" % (THETA_GF_DEG, m2))
    # LC4's rate signal is ~1e-2 rad/frame, so DNp02's raw membrane (0.02) sits at the noise floor. One gain puts it on the GF's
    # membrane scale, and then DNp02 shares the GF threshold.
    return gf, gf, float(gf / m2)


def unit_factors(bio: BioStrictParams) -> tuple[float, float]:
    old = make(dataclasses.replace(bio, clip_hz=50.0, spike_amp_hz=50.0))
    new = make(bio)
    tt, dl = [], []
    for lv in (20, 40, 80):
        a, b = run_disc(old, lv), run_disc(new, lv)
        tt.append(max(r["ttmn"] for r in b) / max(max(r["ttmn"] for r in a), 1e-9))
        dl.append(max(r["dlmn"] for r in b) / max(max(r["dlmn"] for r in a), 1e-9))
    print("unit factors per l/v 20/40/80: TTMn", [round(x, 2) for x in tt], "DLMn", [round(x, 2) for x in dl])
    return float(np.mean(tt)), float(np.mean(dl))


def report(label: str, p: FullPolicy) -> None:
    print(f"== {label}  (g: jump {p.jump_network.g:.3f}, dnp02 {p.dnp02_network.g:.3f}, takeoff {p.takeoff_network.g:.3f}, speed "
          f"{p.speed_network.g:.3f}, steering {p.steering_network.g:.3f}, mdn {p.mdn_network.g:.3f})")
    rs = rest_test(p)
    print("   rest (2000 frames, sigma 0.015): TTMn %.3f DNp01 %.3f DNp02 %.3f DLMn %.3f | spikes GF %d DNp02 %d" % (
        rs["ttmn"], rs["dnp01"], rs["dnp02"], rs["dlmn"], rs["gf_spikes"], rs["dnp02_spikes"]))
    for lv in LV_MS:
        rec = run_disc(p, lv)
        print(f"   l/v {lv:2d} ms: GF {fire(rec, 'spike'):28s} | DNp02 {fire(rec, 'spike2'):28s} | peak TTMn {max(r['ttmn'] for r in rec):6.2f} "
              f"DLMn {max(r['dlmn'] for r in rec):5.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shuffles", type=int, default=5)
    ap.add_argument("--apply", action="store_true", help="use the derived values for the report (default: the values in params)")
    args = ap.parse_args()
    bio = BioStrictParams()
    gf, d2, gain = derive(bio)
    tt, dl = unit_factors(dataclasses.replace(bio, gf_threshold=gf, dnp02_threshold=d2, dnp02_input_gain=gain))
    print(f"\nDERIVED: gf_threshold {gf:.5f}  dnp02_threshold {d2:.5f}  dnp02_input_gain {gain:.3f}  ttmn_unit_factor {tt:.3f}  dlmn_unit_factor {dl:.3f}\n")
    bio = dataclasses.replace(bio, gf_threshold=gf, dnp02_threshold=d2, dnp02_input_gain=gain, ttmn_unit_factor=tt, dlmn_unit_factor=dl)
    report("REAL connectome (derived values)", make(bio))
    for k in range(1, args.shuffles + 1):
        report(f"SHUFFLED {k} (same values, unchanged)", make(bio, shuffle=k))


if __name__ == "__main__":
    main()
