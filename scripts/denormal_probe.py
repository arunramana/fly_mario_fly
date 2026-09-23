# What this file does, in plain English:
# Measures, without changing anything, how much faster the jump circuit
# would run if neuron values below 1e-30 were rounded to zero (numbers that
# tiny can make the processor slow). Prints how small the values get and
# timings with and without rounding; docs/RUNS.md records the result as
# about 3.2x faster on a realistic input pattern and 4.7x during silence.
"""denormal_probe.py -- read-only: what does `h[h < 1e-30] = 0.0` buy on the
jump circuit, the one circuit that never flushes? Measures it on the real
weight matrix; applies no fix.

Result (docs/RUNS.md, refactor phase 4): ~3.2x under a realistic bursty
trace, ~4.7x under sustained silence -- not the 84x once claimed. Genuine
float64 subnormals do occur. The 1e-30 threshold is far above float64's
denormal boundary (2.2e-308), so it flushes more than denormals.

    .venv/Scripts/python.exe -m scripts.denormal_probe
"""
from __future__ import annotations

import time

import numpy as np

from fly.connectome.load_cached import load as load_jump
from fly.network import dynamics
from fly.network.integrator import Integrator
from fly.network.network import Network
from fly.sensing import sensory

G = 2.0
DNP01_SPIKE_THRESHOLD = 0.5
SPIKE_AMP = 50.0


def load_jump_circuit():
    j_bodies, _, _, _, W_j, _, _ = load_jump(N=60)
    K = W_j.shape[0]
    dnp01_L = ((j_bodies["type"] == "DNp01") & (j_bodies["somaSide"] == "L")).to_numpy()
    dnp01_R = ((j_bodies["type"] == "DNp01") & (j_bodies["somaSide"] == "R")).to_numpy()
    dnp01_idx = np.concatenate([np.where(dnp01_L)[0], np.where(dnp01_R)[0]])
    masks = {
        "lc4_l": ((j_bodies["type"] == "LC4") & (j_bodies["somaSide"] == "L")).to_numpy(),
        "lc4_r": ((j_bodies["type"] == "LC4") & (j_bodies["somaSide"] == "R")).to_numpy(),
        "lplc2_l": ((j_bodies["type"] == "LPLC2") & (j_bodies["somaSide"] == "L")).to_numpy(),
        "lplc2_r": ((j_bodies["type"] == "LPLC2") & (j_bodies["somaSide"] == "R")).to_numpy(),
    }
    return W_j, K, dnp01_idx, masks


def new_network(W_j, dnp01_idx):
    return Network(W_j, Integrator(spike_idx=dnp01_idx, spike_threshold=DNP01_SPIKE_THRESHOLD,
                                    spike_amp=SPIKE_AMP), g=G)


def probe_0_threshold_sanity():
    print("=== 0. threshold sanity ===")
    tiny = np.finfo(np.float64).tiny
    print(f"flush threshold 1e-30 vs float64's real denormal boundary (tiny): {tiny:.3e}")
    print(f"1e-30 is {1e-30 / tiny:.3e}x LARGER than the real denormal boundary -- "
          f"most of what this flush zeroes is not actually a hardware denormal")
    print()


def probe_1_does_h_reach_denormal_range(W_j, K, dnp01_idx):
    print("=== 1. does h reach real denormal magnitude, decaying from a spike? ===")
    net = new_network(W_j, dnp01_idx)
    net.h[dnp01_idx] = 50.0  # start from the clip ceiling, like right after a spike
    I_zero = np.zeros(K)
    thresholds = {
        "1e-30 (flush threshold)": 1e-30, "1e-100": 1e-100, "1e-200": 1e-200,
        "tiny=2.2e-308 (real denormal boundary)": np.finfo(np.float64).tiny,
        "smallest_subnormal=5e-324": np.finfo(np.float64).smallest_subnormal,
    }
    crossed = {}
    max_substeps = 200_000
    real_episode_substeps = 4000 * dynamics.SUBSTEPS  # longest max_frames used anywhere in this project
    for step in range(max_substeps):
        h = net.step(I_zero)
        nz = h[h > 0]
        min_nz = nz.min() if len(nz) else 0.0
        for name, thr in list(thresholds.items()):
            if name not in crossed and 0 < min_nz < thr:
                crossed[name] = step
        if len(crossed) == len(thresholds):
            break
    for name in thresholds:
        step = crossed.get(name)
        if step is None:
            print(f"  never crossed {name} within {max_substeps} substeps")
        else:
            flag = ("WITHIN a real episode's budget" if step <= real_episode_substeps
                    else "EXCEEDS any real episode's substep budget")
            print(f"  crossed {name} at substep {step}  ({flag}, real budget <= {real_episode_substeps})")
    print()


def probe_2_timing_worst_case(W_j, K, dnp01_idx, n_substeps=50_000):
    print("=== 2. timing: worst case, sustained silence after one spike ===")

    def run(flush):
        net = new_network(W_j, dnp01_idx)
        net.h[dnp01_idx] = 50.0
        I = np.zeros(K)
        t0 = time.perf_counter()
        for _ in range(n_substeps):
            net.step(I)
            if flush:
                net.flush_denormals()
        return time.perf_counter() - t0

    t_no, t_yes = run(False), run(True)
    print(f"  {n_substeps} substeps, WITHOUT flush: {t_no:.3f}s")
    print(f"  {n_substeps} substeps, WITH flush:    {t_yes:.3f}s")
    print(f"  ratio (no_flush/flush): {t_no / t_yes:.2f}x")
    print()


def probe_3_timing_realistic(W_j, K, dnp01_idx, masks):
    print("=== 3. timing: realistic bursty trace (this project's own Diagnostic-4 realism) ===")
    theta_L, dtheta_L, theta_R, dtheta_R, _ = sensory.sustained_bilateral_trace(
        n_bursts=4, burst_frames=500, quiet_frames=250, seed=0)
    n_frames = len(theta_L)
    print(f"  {n_frames} frames")

    def run(flush):
        net = new_network(W_j, dnp01_idx)
        t0 = time.perf_counter()
        min_nz_seen, n_spikes = 1.0, 0
        for f in range(n_frames):
            I = np.zeros(K)
            I[masks["lc4_l"]] = abs(dtheta_L[f]); I[masks["lplc2_l"]] = theta_L[f]
            I[masks["lc4_r"]] = abs(dtheta_R[f]); I[masks["lplc2_r"]] = theta_R[f]
            for _ in range(dynamics.SUBSTEPS):
                h = net.step(I)
                if flush:
                    net.flush_denormals()
                if net.just_spiked.any():
                    n_spikes += 1
            nz = h[h > 0]
            if len(nz):
                min_nz_seen = min(min_nz_seen, nz.min())
        return time.perf_counter() - t0, min_nz_seen, n_spikes

    dt_no, min_no, spikes_no = run(False)
    dt_yes, min_yes, spikes_yes = run(True)
    print(f"  WITHOUT flush: {dt_no:.3f}s  min nonzero h reached: {min_no:.3e}  spikes: {spikes_no}")
    print(f"  WITH flush:    {dt_yes:.3f}s  min nonzero h reached: {min_yes:.3e}  spikes: {spikes_yes}")
    print(f"  ratio (no_flush/flush): {dt_no / dt_yes:.3f}x")
    print(f"  spike count identical: {spikes_no == spikes_yes} "
          f"(the decision-relevant output; does not by itself prove byte-identical h)")


if __name__ == "__main__":
    W_j, K, dnp01_idx, masks = load_jump_circuit()
    probe_0_threshold_sanity()
    probe_1_does_h_reach_denormal_range(W_j, K, dnp01_idx)
    probe_2_timing_worst_case(W_j, K, dnp01_idx)
    probe_3_timing_realistic(W_j, K, dnp01_idx, masks)
