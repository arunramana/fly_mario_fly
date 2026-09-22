"""
tune_dnp02.py -- SPEC_second_escape.md: pick G_DNP02, DNP02_SPIKE_THRESHOLD,
DNP02_INTEGRATION_ALPHA by simulating the REAL DNp01 and DNp02 circuits
side by side, under both a slow-rising threat and a fast/sudden one --
before ever touching the emulator (same discipline as tune.py/SPEC_jump.md
section 3). The whole point of a second pathway is that it wins the slow
case and loses (or ties) the fast case; if that's not true in the pure
circuit simulation, it will not be true in the game either.

    .venv/Scripts/python.exe tune_dnp02.py
"""
from __future__ import annotations

import numpy as np

import dynamics
from load_cached import load as load_jump
from load_dnp02_cached import load as load_dnp02
from run_mario import DNP01_SPIKE_THRESHOLD, SPIKE_AMP, G

SUBSTEPS = dynamics.SUBSTEPS


def make_jump_masks(bodies):
    lc4_l = ((bodies["type"] == "LC4") & (bodies["somaSide"] == "L")).to_numpy()
    lc4_r = ((bodies["type"] == "LC4") & (bodies["somaSide"] == "R")).to_numpy()
    lplc2_l = ((bodies["type"] == "LPLC2") & (bodies["somaSide"] == "L")).to_numpy()
    lplc2_r = ((bodies["type"] == "LPLC2") & (bodies["somaSide"] == "R")).to_numpy()
    dnp01_r = ((bodies["type"] == "DNp01") & (bodies["somaSide"] == "R")).to_numpy()
    dnp01_idx = np.where(dnp01_r)[0]
    return lc4_l, lc4_r, lplc2_l, lplc2_r, dnp01_idx


def make_dnp02_masks(bodies):
    lc4_r = ((bodies["type"] == "LC4") & (bodies["somaSide"] == "R")).to_numpy()
    dnp02_r = ((bodies["type"] == "DNp02") & (bodies["somaSide"] == "R")).to_numpy()
    dnp02_idx = np.where(dnp02_r)[0]
    return lc4_r, dnp02_idx


def run_trace(theta_trace, dtheta_trace, W_j, lc4_r, lplc2_r, dnp01_idx,
              W_d, lc4_r_d, dnp02_idx, g_dnp02, dnp02_threshold, dnp02_alpha,
              lc4_all_r=None):
    """DNp02's sensory drive is the JUMP CIRCUIT's own real, already-
    recurrently-amplified LC4-R output (hj[lc4_all_r].mean()), not a
    from-scratch re-derivation from raw dtheta -- DNp02's own subgraph only
    captured 8 of 126 real LC4->DNp02 partners (the ones individually
    clearing the N=60 threshold), which is nowhere near enough of LC4's
    own dense lateral recurrence (18,392 synapses / 5,334 pairs, SPEC_jump
    section 1) to reach a comparable activation from raw dtheta alone --
    confirmed empirically (peak ~0.099 even at g=1.74, the edge of
    stability). Reading the real, already-amplified population output
    instead is the same one-directional-read pattern takeoff_circuit
    already uses for DNp01's output onto GFC1-4."""
    Kj = W_j.shape[0]
    Kd = W_d.shape[0]
    jump_state = dynamics.HybridState(Kj, dnp01_idx, spike_threshold=DNP01_SPIKE_THRESHOLD,
                                       spike_amp=SPIKE_AMP)
    dnp02_state = dynamics.HybridState(Kd, dnp02_idx, spike_threshold=dnp02_threshold,
                                        spike_amp=SPIKE_AMP)
    dnp01_commit_frame = None
    dnp02_commit_frame = None
    for frame, (theta, dtheta) in enumerate(zip(theta_trace, dtheta_trace)):
        Ij = np.zeros(Kj)
        Ij[lplc2_r] = theta
        Ij[lc4_r] = abs(dtheta)
        hj = jump_state.h
        Id = np.zeros(Kd)
        Id[lc4_r_d] = hj[lc4_all_r].mean() if lc4_all_r is not None else abs(dtheta)
        for _ in range(SUBSTEPS):
            hj = jump_state.step(W_j, G, Ij)
            Id[lc4_r_d] = hj[lc4_all_r].mean() if lc4_all_r is not None else abs(dtheta)
            dnp02_state.step(W_d, g_dnp02, Id, alpha=dnp02_alpha)
        if dnp01_commit_frame is None and jump_state.just_spiked.any():
            dnp01_commit_frame = frame
        if dnp02_commit_frame is None and dnp02_state.just_spiked.any():
            dnp02_commit_frame = frame
        if dnp01_commit_frame is not None and dnp02_commit_frame is not None:
            break
    return dnp01_commit_frame, dnp02_commit_frame


def slow_ramp(n=400, d0=300.0, v=1.0, w=16.0, d_min=10.0):
    d = np.maximum(d0 - v * np.arange(n), d_min)
    theta = 2.0 * np.arctan(w / (2.0 * d))
    dtheta = np.diff(theta, prepend=theta[0])
    return theta, dtheta


def fast_loom(n=400, d0=300.0, v=6.0, w=16.0, d_min=10.0):
    d = np.maximum(d0 - v * np.arange(n), d_min)
    theta = 2.0 * np.arctan(w / (2.0 * d))
    dtheta = np.diff(theta, prepend=theta[0])
    return theta, dtheta


def main():
    print("Loading jump circuit (unchanged, cached) and DNp02 circuit (cached)...")
    j_bodies, _, _, _, W_j, _, _ = load_jump(N=60)
    lc4_l, lc4_r, lplc2_l, lplc2_r, dnp01_idx = make_jump_masks(j_bodies)
    d_bodies, _, _, _, W_d, _, _ = load_dnp02(N=60)
    lc4_r_d, dnp02_idx = make_dnp02_masks(d_bodies)

    rho1 = dynamics.np.linalg.eigvals(W_d).__abs__().max()
    print(f"W_dnp02 spectral radius (g=1): {rho1:.4f} -> linear boundary near g~{1/rho1:.2f}\n")

    print("--- sweep DNP02_SPIKE_THRESHOLD x DNP02_INTEGRATION_ALPHA on a SLOW ramp "
          "(should commit clearly before DNp01) -- driven by the jump circuit's "
          "REAL LC4-R output, not raw dtheta re-derived from scratch ---")
    theta_s, dtheta_s = slow_ramp()
    for g_dnp02 in (1.0, 1.4, 1.7):
        for thresh in (0.05, 0.1, 0.15, 0.2, 0.3):
            for alpha in (0.03, 0.05, 0.08, 0.1):
                f01, f02 = run_trace(theta_s, dtheta_s, W_j, lc4_r, lplc2_r, dnp01_idx,
                                      W_d, lc4_r_d, dnp02_idx, g_dnp02, thresh, alpha,
                                      lc4_all_r=lc4_r)
                lead = (f01 - f02) if (f01 is not None and f02 is not None) else None
                print(f"  g={g_dnp02} thresh={thresh:<5} alpha={alpha:<5} "
                      f"DNp01@{f01} DNp02@{f02} DNp02_leads_by={lead}")

    print("\n--- verify FAST loom: DNp01 should still win (or tie) on latency, "
          "at the chosen thresh/alpha ---")
    theta_f, dtheta_f = fast_loom()
    for g_dnp02, thresh, alpha in ((1.4, 0.15, 0.08),):
        f01, f02 = run_trace(theta_f, dtheta_f, W_j, lc4_r, lplc2_r, dnp01_idx,
                              W_d, lc4_r_d, dnp02_idx, g_dnp02, thresh, alpha,
                              lc4_all_r=lc4_r)
        print(f"  g={g_dnp02} thresh={thresh} alpha={alpha}: DNp01@{f01} DNp02@{f02}")


if __name__ == "__main__":
    main()
