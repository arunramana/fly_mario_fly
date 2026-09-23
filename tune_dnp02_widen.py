"""
tune_dnp02_widen.py -- SPEC_second_escape.md follow-up: does lowering
DNp02's own N threshold (60 -> 30 -> 15 -> 5) restore a genuine,
STABLE early-commit advantage over DNp01, or does the null from N=60 hold?

Only searches g values with a comfortable safety margin below each
circuit's own real spectral-radius boundary (g <= 0.85 / rho) -- SPEC's own
instruction: a result that needs a fragile parameter is not a result.

    .venv/Scripts/python.exe tune_dnp02_widen.py
"""
from __future__ import annotations

import numpy as np

from fly.network import dynamics
from fly.circuits import dnp02_circuit
from run_mario import SPIKE_AMP, DNP01_SPIKE_THRESHOLD, G
from fly.connectome.load_cached import load as load_jump
from tune_dnp02 import make_jump_masks, slow_ramp, fast_loom

SAFETY = 0.85


def dnp01_baseline(theta, dtheta, W_j, lc4_r, lplc2_r, dnp01_idx):
    Kj = W_j.shape[0]
    st = dynamics.HybridState(Kj, dnp01_idx, spike_threshold=DNP01_SPIKE_THRESHOLD, spike_amp=SPIKE_AMP)
    for frame, (th, dth) in enumerate(zip(theta, dtheta)):
        I = np.zeros(Kj); I[lplc2_r] = th; I[lc4_r] = abs(dth)
        for _ in range(dynamics.SUBSTEPS):
            st.step(W_j, G, I)
            if st.just_spiked.any():
                return frame
    return None


def dnp02_commit(W_d, lc4_r_d, dnp02_idx, dtheta, g, thresh, alpha_ema):
    Kd = W_d.shape[0]
    st = dynamics.HybridState(Kd, dnp02_idx, spike_threshold=thresh, spike_amp=SPIKE_AMP)
    ema = 0.0
    for frame, dth in enumerate(dtheta):
        ema = (1 - alpha_ema) * ema + alpha_ema * abs(dth)
        I = np.zeros(Kd); I[lc4_r_d] = ema
        for _ in range(dynamics.SUBSTEPS):
            st.step(W_d, g, I)
            if st.just_spiked.any():
                return frame
    return None


def main():
    print("Loading jump circuit (unchanged, cached)...")
    j_bodies, _, _, _, W_j, _, _ = load_jump(N=60)
    lc4_l, lc4_r, lplc2_l, lplc2_r, dnp01_idx = make_jump_masks(j_bodies)

    theta_s, dtheta_s = slow_ramp(v=1.0)
    theta_f, dtheta_f = fast_loom(v=6.0)
    d01_s = dnp01_baseline(theta_s, dtheta_s, W_j, lc4_r, lplc2_r, dnp01_idx)
    d01_f = dnp01_baseline(theta_f, dtheta_f, W_j, lc4_r, lplc2_r, dnp01_idx)
    print(f"DNp01 baseline: slow_commit={d01_s}  fast_commit={d01_f}\n")

    for N in (60, 30, 15, 5):
        print(f"=== N={N} ===")
        bodies, edges, total_input, signs, W_d, order, diag = dnp02_circuit.build_full(N=N)
        lc4_r_d = ((bodies["type"] == "LC4") & (bodies["somaSide"] == "R")).to_numpy()
        dnp02_l = ((bodies["type"] == "DNp02") & (bodies["somaSide"] == "L")).to_numpy()
        dnp02_r = ((bodies["type"] == "DNp02") & (bodies["somaSide"] == "R")).to_numpy()
        dnp02_idx = np.concatenate([np.where(dnp02_l)[0], np.where(dnp02_r)[0]])
        n_lc4 = int(lc4_r_d.sum()) + int(((bodies["type"] == "LC4") & (bodies["somaSide"] == "L")).sum())

        rho = float(np.abs(np.linalg.eigvals(W_d)).max())
        g_max = SAFETY / rho
        print(f"  {len(bodies)} neurons, {n_lc4} LC4 partners, "
              f"spectral radius(g=1)={rho:.4f}, safe g <= {g_max:.3f}")

        best = None  # (slow_lead, g, thresh, alpha, fs, ff)
        for g in np.linspace(0.3, g_max, 8):
            for thresh in (0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8):
                for alpha in (0.02, 0.05, 0.08, 0.1, 0.15, 0.2):
                    fs = dnp02_commit(W_d, lc4_r_d, dnp02_idx, dtheta_s, g, thresh, alpha)
                    if fs is None:
                        continue
                    slow_lead = (d01_s - fs) if d01_s is not None else None
                    if slow_lead is None or slow_lead <= 0:
                        continue
                    ff = dnp02_commit(W_d, lc4_r_d, dnp02_idx, dtheta_f, g, thresh, alpha)
                    fast_lead = (d01_f - ff) if (d01_f is not None and ff is not None) else None
                    if best is None or slow_lead > best[0]:
                        best = (slow_lead, g, thresh, alpha, fs, ff, fast_lead)

        if best is None:
            print(f"  NO stable (g<={g_max:.3f}) combo found where DNp02 out-commits DNp01 "
                  f"on the slow ramp at all.")
        else:
            slow_lead, g, thresh, alpha, fs, ff, fast_lead = best
            print(f"  BEST: g={g:.3f} thresh={thresh} alpha={alpha}")
            print(f"    slow ramp: DNp01@{d01_s} DNp02@{fs}  DNp02 leads by {slow_lead} frames")
            print(f"    fast loom: DNp01@{d01_f} DNp02@{ff}  "
                  f"{'DNp02 also wins fast by ' + str(fast_lead) if (fast_lead is not None and fast_lead > 0) else 'DNp01 wins/ties fast (as intended)'}")
        print()


if __name__ == "__main__":
    main()
