# What this file does, in plain English:
# A test bench for the fly's escape circuit that needs no game. It plays a standard "looming
# disc" (a dot that grows the way an approaching object does, at a chosen speed) into the
# circuit and records how the Giant Fiber, the jump muscle neuron and the second escape
# neuron respond as the collision nears; and it runs the circuit with no input at all but
# noise to check nothing switches itself on. Used to calibrate and test bio_strict.
"""bridge/loom_disc.py -- docs/SPEC_bio_calibration.md. Inputs are exactly what FullPolicy gives the circuit: |dtheta|
(rad/frame) into LC4 and theta (rad) into LPLC2 (both hemispheres: a frontal object), the EMA of |dtheta| into the DNp02
pool's LC4, DNp01 -> takeoff circuit -> DLMn. `theta(t) = 2 atan((l/v) / tau)`, tau = time to collision."""

from __future__ import annotations

import math

import numpy as np

from fly.network import dynamics

FRAME_MS = 1000.0 / 60.0
LV_MS = (10, 20, 40, 80)
THETA0_DEG = 2.0


def reset_networks(p) -> None:
    """Zero every network's activity, spike-cell membrane and refractory counters."""
    for net in (p.jump_network, p.dnp02_network, p.takeoff_network, p.speed_network, p.steering_network, p.mdn_network):
        net.h[:] = 0.0
        integ = net.integrator
        if len(integ.spike_idx):
            integ.mem[:] = 0.0
            integ._refractory_left[:] = 0
            integ.just_spiked = np.zeros(len(integ.spike_idx), dtype=bool)


def _step_escape(p, Ij, Idp, noise):
    """One frame (`substeps` substeps) of the jump, takeoff and DNp02 networks; returns their outputs and whether each
    spiked at any substep, plus the largest spike-cell membrane seen."""
    sp1 = sp2 = False
    mem1 = mem2 = 0.0
    for _ in range(p.substeps):
        h = p.jump_network.step(Ij, noise=noise)
        It = np.zeros(p.Kt)
        It[p.takeoff_dnp01_mask] = h[p.jump_dnp01_mask]
        ht = p.takeoff_network.step(It, noise=noise)
        h2 = p.dnp02_network.step(Idp, noise=noise)
        sp1 |= bool(p.jump_network.just_spiked.any())
        sp2 |= bool(p.dnp02_network.just_spiked.any())
        mem1 = max(mem1, float(p.jump_network.integrator.mem.max()))
        mem2 = max(mem2, float(p.dnp02_network.integrator.mem.max()))
    return h, ht, h2, sp1, sp2, mem1, mem2


def run_disc(p, lv_ms: float, sigma: float = 0.0, seed: int = 0) -> list[dict]:
    """One looming disc into FullPolicy `p`'s escape circuit. One record per 16.7 ms frame."""
    c = p.config
    tau0 = lv_ms / math.tan(math.radians(THETA0_DEG) / 2.0)
    reset_networks(p)
    noise = dynamics.NoiseConfig(sigma, np.random.default_rng(seed))
    ema = 0.0
    prev = 0.0
    out = []
    for f in range(int(tau0 / FRAME_MS) + 3):
        tau = tau0 - f * FRAME_MS
        if tau <= 0:
            break
        th = 2.0 * math.atan(lv_ms / tau)
        dth, prev = th - prev, th
        ema = (1 - c.dnp02.alpha) * ema + c.dnp02.alpha * abs(dth)
        Ij = np.zeros(p.Kj)
        for s in "LR":
            Ij[p.j_msk[f"LC4_{s}"]] = abs(dth)
            Ij[p.j_msk[f"LPLC2_{s}"]] = th
        Idp = np.zeros(p.Kdp)
        Idp[p.dnp02_lc4_l] = Idp[p.dnp02_lc4_r] = ema * (c.bio.dnp02_input_gain if p.bio else 1.0)
        h, ht, h2, sp1, sp2, mem1, mem2 = _step_escape(p, Ij, Idp, noise)
        out.append(dict(tau=tau, theta=math.degrees(th), mem=mem1, mem2=mem2, spike=sp1, spike2=sp2,
                        dnp01=float(h[p.jump_dnp01_mask].mean()),
                        ttmn=float(max(h[p.j_msk["TTMn_L"]].mean(), h[p.j_msk["TTMn_R"]].mean())),
                        dlmn=float(ht[p.dlmn_mask].mean()),
                        ttmn2=float(max(h2[p.dnp02_ttmn_l].mean(), h2[p.dnp02_ttmn_r].mean()))))
    return out


def first(rec: list[dict], key: str):
    """First record where boolean `key` is true (or None)."""
    return next((r for r in rec if r[key]), None)


def rest_test(p, frames: int = 2000, sigma: float = 0.015, seed: int = 0) -> dict:
    """No stimulus, noise only. Returns the max over the last 3/4 of the run of TTMn, DNp01, DNp02, DLMn and the spike counts."""
    reset_networks(p)
    noise = dynamics.NoiseConfig(sigma, np.random.default_rng(seed))
    Ij, Idp = np.zeros(p.Kj), np.zeros(p.Kdp)
    rows = []
    for f in range(frames):
        h, ht, h2, sp1, sp2, _m1, _m2 = _step_escape(p, Ij, Idp, noise)
        rows.append((max(h[p.j_msk["TTMn_L"]].mean(), h[p.j_msk["TTMn_R"]].mean()), float(h[p.jump_dnp01_mask].mean()),
                     float(h2[p.dnp02_idx].mean()), float(ht[p.dlmn_mask].mean()), sp1, sp2))
    a = np.array(rows, dtype=float)[frames // 4:]
    return {"ttmn": float(a[:, 0].max()), "dnp01": float(a[:, 1].max()), "dnp02": float(a[:, 2].max()),
            "dlmn": float(a[:, 3].max()), "gf_spikes": int(a[:, 4].sum()), "dnp02_spikes": int(a[:, 5].sum())}
