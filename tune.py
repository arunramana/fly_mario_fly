"""
tune.py — synthetic-looming harness for tuning g, per SPEC_jump.md section 3.

No Mario, no RAM, no rendering. An object of fixed width approaches at
constant velocity; theta(t) is fed straight to the LC4/LPLC2 populations of
one hemisphere. Sweep g and check the three diagnostics the spec asks for
before this circuit is ever allowed near an emulator.

    python tune.py
"""

from __future__ import annotations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fly.connectome import circuit
from fly.network import dynamics
from fly.sensing.sensory import DRIVEN_SIDE, W_TILE, theta_ramp, masks, sensory_trace  # noqa: F401


def diag_zero_input_decay(W, g, K, n_frames=40):
    rng = np.random.default_rng(0)
    h0 = rng.uniform(0.2, 0.8, K)
    I_trace = np.zeros((n_frames, K))
    hist = dynamics.simulate(W, g, I_trace, h0=h0)
    start_norm = np.linalg.norm(hist[0])
    end_norm = np.linalg.norm(hist[-1])
    decayed = end_norm < 1e-3 * start_norm
    return {"pass": bool(decayed), "start_norm": start_norm, "end_norm": end_norm,
            "ratio": end_norm / start_norm}


def diag_pulse_no_ringing(W, g, K, msk, n_frames=40, pulse_frames=1):
    I_trace = np.zeros((n_frames, K))
    I_trace[:pulse_frames, msk["LC4_drive"]] = 0.2
    I_trace[:pulse_frames, msk["LPLC2_drive"]] = 0.5
    hist = dynamics.simulate(W, g, I_trace)
    dnp01 = hist[:, msk["DNp01_drive"]].mean(axis=1)

    peak_i = int(np.argmax(dnp01))
    post = dnp01[peak_i:]
    # local maxima strictly after the main peak, with prominence above 1% of it
    peak_val = dnp01[peak_i] if dnp01[peak_i] > 0 else 1.0
    rebounds = 0
    for i in range(1, len(post) - 1):
        if post[i] > post[i - 1] and post[i] > post[i + 1] and post[i] > 0.01 * peak_val:
            rebounds += 1
    transient_died = post[-1] < 0.05 * peak_val if peak_val > 0 else True
    return {"pass": bool(rebounds == 0 and transient_died), "rebounds": rebounds,
            "peak": float(dnp01[peak_i]), "end": float(dnp01[-1]), "trace": dnp01}


def diag_looming_sharp_late(W, g, K, msk, theta, dtheta):
    n_frames = len(theta)
    I_trace = sensory_trace(K, msk, theta, dtheta)
    hist = dynamics.simulate(W, g, I_trace)
    substeps = dynamics.SUBSTEPS
    # value at the END of each frame (after its substeps), one point per frame
    frame_idx = np.arange(1, n_frames + 1) * substeps
    dnp01 = hist[frame_idx, :][:, msk["DNp01_drive"]].mean(axis=1)
    lc4 = hist[frame_idx, :][:, msk["LC4_all"]].mean(axis=1)
    lplc2 = hist[frame_idx, :][:, msk["LPLC2_all"]].mean(axis=1)

    def rise_fractions(y):
        ymax = y.max()
        if ymax <= 1e-9:
            return None
        y_norm = y / ymax
        t10 = np.argmax(y_norm >= 0.1) if (y_norm >= 0.1).any() else n_frames - 1
        t50 = np.argmax(y_norm >= 0.5) if (y_norm >= 0.5).any() else n_frames - 1
        t90 = np.argmax(y_norm >= 0.9) if (y_norm >= 0.9).any() else n_frames - 1
        return {"t10": t10 / n_frames, "t50": t50 / n_frames, "t90": t90 / n_frames,
                "rise_width": (t90 - t10) / n_frames}

    dnp01_r = rise_fractions(dnp01)
    theta_r = rise_fractions(theta)

    if dnp01_r is None:
        return {"pass": False, "reason": "DNp01 never activates", "dnp01": dnp01,
                "lc4": lc4, "lplc2": lplc2, "theta": theta, "dtheta": dtheta}

    late = dnp01_r["t50"] > 0.7
    sharp = dnp01_r["rise_width"] < 0.15
    sharper_than_theta = dnp01_r["rise_width"] < 0.5 * theta_r["rise_width"]
    ok = late and sharp and sharper_than_theta
    return {"pass": bool(ok), "late": late, "sharp": sharp,
            "sharper_than_theta": sharper_than_theta,
            "dnp01_rise": dnp01_r, "theta_rise": theta_r,
            "dnp01": dnp01, "lc4": lc4, "lplc2": lplc2, "theta": theta, "dtheta": dtheta}


def sweep(W, bodies, order, g_values):
    K = W.shape[0]
    msk = masks(bodies)
    d, theta, dtheta = theta_ramp()

    rows = []
    for g in g_values:
        d1 = diag_zero_input_decay(W, g, K)
        d2 = diag_pulse_no_ringing(W, g, K, msk)
        d3 = diag_looming_sharp_late(W, g, K, msk, theta, dtheta)
        rho = circuit.spectral_radius(W, g)
        rows.append({
            "g": g, "rho_gW": rho,
            "decays_to_zero": d1["pass"], "decay_ratio": d1["ratio"],
            "no_ringing": d2["pass"], "rebounds": d2["rebounds"],
            "sharp_late": d3["pass"],
            "t50_frac": d3.get("dnp01_rise", {}).get("t50"),
            "rise_width_frac": d3.get("dnp01_rise", {}).get("rise_width"),
            "all_three": d1["pass"] and d2["pass"] and d3["pass"],
        })
    return rows, (d, theta, dtheta)


def print_sweep(rows):
    print(f"\n{'g':>6} {'rho(gW)':>8} {'decay->0':>9} {'ratio':>10} "
          f"{'no ring':>8} {'rebnd':>6} {'sharp+late':>11} {'t50':>6} {'rise_w':>7} {'ALL 3':>6}")
    for r in rows:
        print(f"{r['g']:6.3f} {r['rho_gW']:8.4f} {str(r['decays_to_zero']):>9} "
              f"{r['decay_ratio']:10.2e} {str(r['no_ringing']):>8} {r['rebounds']:6d} "
              f"{str(r['sharp_late']):>11} "
              f"{('%.2f' % r['t50_frac']) if r['t50_frac'] is not None else '  -  ':>6} "
              f"{('%.3f' % r['rise_width_frac']) if r['rise_width_frac'] is not None else '  -  ':>7} "
              f"{str(r['all_three']):>6}")


def plot_chosen(W, bodies, g, path="tune_diagnostics.png"):
    K = W.shape[0]
    msk = masks(bodies)
    d, theta, dtheta = theta_ramp()

    d1 = diag_zero_input_decay(W, g, K)
    d2 = diag_pulse_no_ringing(W, g, K, msk)
    d3 = diag_looming_sharp_late(W, g, K, msk, theta, dtheta)

    fig, axes = plt.subplots(3, 1, figsize=(8, 10))

    n1 = 40
    h0 = np.random.default_rng(0).uniform(0.2, 0.8, K)
    hist1 = dynamics.simulate(W, g, np.zeros((n1, K)), h0=h0)
    t1 = np.arange(len(hist1)) / dynamics.SUBSTEPS
    axes[0].plot(t1, np.linalg.norm(hist1, axis=1))
    axes[0].set_title(f"1. Zero input, h0 random -- decay to zero? "
                       f"{'PASS' if d1['pass'] else 'FAIL'} (g={g})")
    axes[0].set_xlabel("frame")
    axes[0].set_ylabel("||h||")

    axes[1].plot(d2["trace"] / dynamics.SUBSTEPS if False else np.arange(len(d2["trace"])) / dynamics.SUBSTEPS,
                 d2["trace"])
    axes[1].set_title(f"2. Brief pulse -- transient dies, no ringing? "
                       f"{'PASS' if d2['pass'] else 'FAIL'} "
                       f"(rebounds={d2['rebounds']})")
    axes[1].set_xlabel("frame")
    axes[1].set_ylabel("DNp01 (driven side)")

    frames = np.arange(1, len(theta) + 1)
    ax = axes[2]
    ax.plot(frames, theta / theta.max(), label="theta (normalised)", linestyle="--", color="gray")
    ax.plot(frames, d3["lc4"] / max(d3["lc4"].max(), 1e-9), label="LC4 mean", alpha=0.7)
    ax.plot(frames, d3["lplc2"] / max(d3["lplc2"].max(), 1e-9), label="LPLC2 mean", alpha=0.7)
    ax.plot(frames, d3["dnp01"] / max(d3["dnp01"].max(), 1e-9), label="DNp01 (driven side)", linewidth=2, color="crimson")
    ax.set_title(f"3. Looming ramp -- sharp, late DNp01 rise? "
                 f"{'PASS' if d3['pass'] else 'FAIL'} "
                 f"(t50={d3['dnp01_rise']['t50']:.2f}, rise_width={d3['dnp01_rise']['rise_width']:.3f})")
    ax.set_xlabel("frame")
    ax.set_ylabel("normalised activity")
    ax.legend(loc="upper left", fontsize=8)

    fig.suptitle(f"Synthetic-looming diagnostics at g = {g}  (spectral radius of g*W = {circuit.spectral_radius(W, g):.3f})")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"\nSaved diagnostic plot -> {path}")
    return d1, d2, d3


if __name__ == "__main__":
    bodies, edges, total_input, signs, W, order, diag = circuit.build()

    g_values = [0.3, 0.5, 0.7, 0.85, 0.9, 0.95, 0.98, 1.0, 1.02, 1.05, 1.1, 1.3, 1.5, 2.0]
    rows, (d, theta, dtheta) = sweep(W, bodies, order, g_values)
    print_sweep(rows)

    winners = [r for r in rows if r["all_three"]]
    if winners:
        chosen = max(winners, key=lambda r: r["g"])
        print(f"\nChosen g = {chosen['g']} -- largest g that passes all three "
              f"diagnostics (closest to the instability boundary without "
              f"crossing it, for the sharpest commitment).")
    else:
        print("\nNo g in the sweep passes all three diagnostics simultaneously. "
              "Reporting that rather than picking the least-bad option.")
        chosen = None

    if chosen:
        plot_chosen(W, bodies, chosen["g"])
    else:
        best_sharp = max(rows, key=lambda r: (r["decays_to_zero"] and r["no_ringing"],
                                               -(r["rise_width_frac"] or 1.0)))
        plot_chosen(W, bodies, best_sharp["g"], path="tune_diagnostics_no_winner.png")
