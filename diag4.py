"""
diag4.py -- SPEC_jump.md section 3, "Diagnostic 4 -- sustained input."

A single ramp-from-rest (tune.py's diagnostics 1-3) never tests what the game
actually delivers: enemies approach, pass, and reappear on BOTH hemispheres
for thousands of frames, often overlapping, with no reset between them. This
replays a >=2000-step bilateral, bursty trace through the EXACT system
run_mario.py drives Mario with -- the expanded N=60 circuit plus the DNp01
spiking fallback (HybridState) -- and asserts the four conditions section 3
lists:

  1. LC4_mean / LPLC2_mean vary with theta across the whole trace (report
     correlation; near zero means saturated).
  2. No unit sits at the clip ceiling for more than a brief transient.
  3. Activity returns toward baseline in the gaps between approaches.
  4. TTMn crosses its press threshold on approaches and not in the gaps.

A gentler single-hemisphere, cleanly-gapped trace (`sensory.theta_multi_
approach`) does NOT reproduce the saturation the real run showed -- it was
tried first here and passes condition 2/3 trivially because nothing ever
overlaps. `sensory.sustained_bilateral_trace` is what actually catches it:
overlapping approaches on both hemispheres are what the real level delivers,
and what the single-ramp tuning in tune.py never exercised.

    python diag4.py                  # current run_mario.py config (expect FAIL)
    python diag4.py --g 0.9          # test one g
    python diag4.py --sweep          # search for a passing g
"""

from __future__ import annotations

import argparse

import numpy as np

import dynamics
from load_cached import load
from sensory import masks, sustained_bilateral_trace

# thresholds for what counts as "passes" -- these are diagnostic acceptance
# criteria, not model parameters; they do not count against CLAUDE.md's
# two-hand-set-scalar budget.
CORR_MIN = 0.3            # LC4/LPLC2 mean vs theta correlation, "not near zero"
CLIP_FRAC_MAX = 0.05      # fraction of substeps a non-DNp01 unit may sit at ceiling
BASELINE_FRAC_MAX = 0.10  # end-of-gap activity, as a fraction of the preceding peak
SETTLE_FRAMES = 30        # grace period after a burst ends before "no TTMn" applies
                           # -- matches JUMP_HOLD_FRAMES (run_mario.py): the muscle
                           # is SUPPOSED to stay activated a few frames after the
                           # stimulus ends to produce a real jump. Only a crossing
                           # that persists past this counts as a stuck/spurious one.

N_BURSTS = 4
BURST_FRAMES = 500
QUIET_FRAMES = 250


def build_masks(bodies):
    mR = masks(bodies, side="R")
    mL = masks(bodies, side="L")
    return {
        "LC4_all": mR["LC4_all"], "LPLC2_all": mR["LPLC2_all"],
        "LC4_drive_L": mL["LC4_drive"], "LPLC2_drive_L": mL["LPLC2_drive"],
        "LC4_drive_R": mR["LC4_drive"], "LPLC2_drive_R": mR["LPLC2_drive"],
        "TTMn_L": ((bodies["type"] == "TTMn") & (bodies["somaSide"] == "L")).to_numpy(),
        "TTMn_R": ((bodies["type"] == "TTMn") & (bodies["somaSide"] == "R")).to_numpy(),
        "DNp01_L": ((bodies["type"] == "DNp01") & (bodies["somaSide"] == "L")).to_numpy(),
        "DNp01_R": ((bodies["type"] == "DNp01") & (bodies["somaSide"] == "R")).to_numpy(),
    }


def run_trace(W, bodies, g, spike_threshold, spike_amp,
              n_bursts=N_BURSTS, burst_frames=BURST_FRAMES, quiet_frames=QUIET_FRAMES,
              substeps=dynamics.SUBSTEPS, alpha=dynamics.ALPHA, seed=0, make_state=None):
    """Drive the deployed HybridState system with the bilateral bursty trace.

    `make_state(K, dnp01_idx, spike_threshold, spike_amp)` overrides the
    state class -- pass one that builds an AdaptiveHybridState to test the
    leak/adaptation hypothesis without duplicating this whole harness.
    """
    K = W.shape[0]
    msk = build_masks(bodies)
    theta_L, dtheta_L, theta_R, dtheta_R, approach = sustained_bilateral_trace(
        n_bursts=n_bursts, burst_frames=burst_frames, quiet_frames=quiet_frames, seed=seed)
    n_frames = len(approach)
    theta = np.maximum(theta_L, theta_R)

    I_trace = np.zeros((n_frames, K))
    I_trace[:, msk["LC4_drive_L"]] = np.abs(dtheta_L)[:, None]
    I_trace[:, msk["LPLC2_drive_L"]] = theta_L[:, None]
    I_trace[:, msk["LC4_drive_R"]] = np.abs(dtheta_R)[:, None]
    I_trace[:, msk["LPLC2_drive_R"]] = theta_R[:, None]

    dnp01_L_idx = np.where(msk["DNp01_L"])[0]
    dnp01_R_idx = np.where(msk["DNp01_R"])[0]
    dnp01_idx = np.concatenate([dnp01_L_idx, dnp01_R_idx])

    if make_state is None:
        st = dynamics.HybridState(K, dnp01_idx, spike_threshold=spike_threshold,
                                   spike_amp=spike_amp)
    else:
        st = make_state(K, dnp01_idx, spike_threshold, spike_amp)
    non_dnp01 = np.ones(K, dtype=bool)
    non_dnp01[dnp01_idx] = False

    lc4_mean = np.empty(n_frames)
    lplc2_mean = np.empty(n_frames)
    ttmn_val = np.empty(n_frames)
    clip_hits = np.zeros(K)
    n_substeps_total = n_frames * substeps

    for f in range(n_frames):
        for _ in range(substeps):
            h = st.step(W, g, I_trace[f], alpha)
            clip_hits += (h >= dynamics.CLIP - 1e-9)
        lc4_mean[f] = h[msk["LC4_all"]].mean()
        lplc2_mean[f] = h[msk["LPLC2_all"]].mean()
        ttmn_val[f] = max(h[msk["TTMn_L"]].mean(), h[msk["TTMn_R"]].mean())

    clip_frac_per_unit = clip_hits / n_substeps_total
    return {
        "theta": theta, "approach": approach,
        "lc4_mean": lc4_mean, "lplc2_mean": lplc2_mean, "ttmn_val": ttmn_val,
        "clip_frac_per_unit": clip_frac_per_unit, "non_dnp01": non_dnp01,
    }


def _segments(mask):
    """Contiguous (start, end) index ranges where mask is True."""
    edges = np.diff(mask.astype(int), prepend=0, append=0)
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]
    return list(zip(starts, ends))


def check_varies_with_theta(theta, lc4_mean, lplc2_mean):
    def corr(x, y):
        if np.std(x) < 1e-12 or np.std(y) < 1e-12:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])
    r_lc4 = corr(theta, lc4_mean)
    r_lplc2 = corr(theta, lplc2_mean)
    ok = r_lc4 > CORR_MIN and r_lplc2 > CORR_MIN
    return {"pass": ok, "r_lc4": r_lc4, "r_lplc2": r_lplc2}


def check_no_sustained_clip(clip_frac_per_unit, non_dnp01):
    frac = clip_frac_per_unit[non_dnp01]
    return {
        "pass": bool(frac.max() < CLIP_FRAC_MAX),
        "max_unit_clip_frac": float(frac.max()),
        "mean_clip_frac": float(frac.mean()),
        "n_units_over_threshold": int((frac >= CLIP_FRAC_MAX).sum()),
    }


def check_returns_to_baseline(approach, lc4_mean, lplc2_mean):
    approach_segs = _segments(approach)
    gap_segs = _segments(~approach)
    ratios = []
    for i, (gs, ge) in enumerate(gap_segs):
        if i >= len(approach_segs):
            break
        as_, ae = approach_segs[i]
        peak = max(lc4_mean[as_:ae].max(), lplc2_mean[as_:ae].max(), 1e-9)
        tail = slice(max(ge - 20, gs), ge)
        end_val = max(lc4_mean[tail].max(), lplc2_mean[tail].max())
        ratios.append(end_val / peak)
    ratios = np.array(ratios)
    return {
        "pass": bool(len(ratios) > 0 and (ratios < BASELINE_FRAC_MAX).all()),
        "max_ratio": float(ratios.max()) if len(ratios) else float("nan"),
        "n_gaps_checked": len(ratios),
        "n_gaps_failed": int((ratios >= BASELINE_FRAC_MAX).sum()),
    }


def check_ttmn_causal(approach, ttmn_val, ttmn_threshold, settle_frames=SETTLE_FRAMES):
    approach_segs = _segments(approach)
    gap_segs = _segments(~approach)
    n_approach_crossed = sum(1 for (s, e) in approach_segs
                              if (ttmn_val[s:e] >= ttmn_threshold).any())
    n_gap_crossed = sum(1 for (s, e) in gap_segs
                         if (ttmn_val[s + settle_frames:e] >= ttmn_threshold).any())
    return {
        "pass": bool(n_approach_crossed == len(approach_segs) and n_gap_crossed == 0),
        "n_approaches": len(approach_segs), "n_approach_crossed": n_approach_crossed,
        "n_gaps": len(gap_segs), "n_gap_crossed": n_gap_crossed,
    }


def diagnostic4(W, bodies, g, spike_threshold, spike_amp, ttmn_threshold,
                 n_bursts=N_BURSTS, burst_frames=BURST_FRAMES, quiet_frames=QUIET_FRAMES,
                 verbose=True, make_state=None, require_spec_minimum=True):
    """`require_spec_minimum=False` only for a fast internal SCREEN (e.g.
    shuffle_sweep.py's coarse g-grid, run on a shorter trace for speed) --
    every reported/confirmed result still goes through the real >=2000-frame
    check before being called a pass."""
    trace = run_trace(W, bodies, g, spike_threshold, spike_amp,
                       n_bursts=n_bursts, burst_frames=burst_frames, quiet_frames=quiet_frames,
                       make_state=make_state)
    n_frames = len(trace["theta"])
    if require_spec_minimum:
        assert n_frames >= 2000, f"trace only {n_frames} frames, spec requires >= 2000"

    c1 = check_varies_with_theta(trace["theta"], trace["lc4_mean"], trace["lplc2_mean"])
    c2 = check_no_sustained_clip(trace["clip_frac_per_unit"], trace["non_dnp01"])
    c3 = check_returns_to_baseline(trace["approach"], trace["lc4_mean"], trace["lplc2_mean"])
    c4 = check_ttmn_causal(trace["approach"], trace["ttmn_val"], ttmn_threshold)
    overall = c1["pass"] and c2["pass"] and c3["pass"] and c4["pass"]

    if verbose:
        print(f"\n=== Diagnostic 4 -- sustained bilateral input (g={g}, "
              f"{n_frames} frames, {n_bursts} bursts of {burst_frames}f / "
              f"{quiet_frames}f quiet) ===")
        print(f"  1. varies with theta   : {'PASS' if c1['pass'] else 'FAIL'}  "
              f"r(LC4,theta)={c1['r_lc4']:+.3f}  r(LPLC2,theta)={c1['r_lplc2']:+.3f}  "
              f"(need > {CORR_MIN})")
        print(f"  2. no sustained clip    : {'PASS' if c2['pass'] else 'FAIL'}  "
              f"max unit clipped {c2['max_unit_clip_frac']*100:.1f}% of substeps, "
              f"mean {c2['mean_clip_frac']*100:.1f}%, "
              f"{c2['n_units_over_threshold']} units over {CLIP_FRAC_MAX*100:.0f}% "
              f"(need < {CLIP_FRAC_MAX*100:.0f}%)")
        print(f"  3. returns to baseline  : {'PASS' if c3['pass'] else 'FAIL'}  "
              f"worst end-of-gap/peak ratio = {c3['max_ratio']:.3f} over "
              f"{c3['n_gaps_checked']} gaps, {c3['n_gaps_failed']} failed "
              f"(need < {BASELINE_FRAC_MAX})")
        print(f"  4. TTMn causal          : {'PASS' if c4['pass'] else 'FAIL'}  "
              f"crossed on {c4['n_approach_crossed']}/{c4['n_approaches']} bursts, "
              f"{c4['n_gap_crossed']}/{c4['n_gaps']} spurious quiet-period crossings "
              f"(after a {SETTLE_FRAMES}f settle grace)")
        print(f"  ALL FOUR: {'PASS' if overall else 'FAIL'}")

    return {"pass": overall, "c1": c1, "c2": c2, "c3": c3, "c4": c4, "trace": trace}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--g", type=float, default=3.5)
    ap.add_argument("--spike-threshold", type=float, default=0.5)
    ap.add_argument("--spike-amp", type=float, default=50.0)
    ap.add_argument("--ttmn-threshold", type=float, default=3.0)
    ap.add_argument("--sweep", action="store_true",
                     help="search a range of g for one that passes all four checks")
    args = ap.parse_args()

    print("Loading the expanded N=60 circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)

    if not args.sweep:
        diagnostic4(W, bodies, args.g, args.spike_threshold, args.spike_amp,
                    args.ttmn_threshold)
    else:
        g_values = [0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 0.85,
                    0.9, 0.95, 1.0, 1.05, 1.1, 1.3, 1.5, 2.0, 3.5]
        results = []
        for g in g_values:
            r = diagnostic4(W, bodies, g, args.spike_threshold, args.spike_amp,
                             args.ttmn_threshold, verbose=False)
            results.append((g, r))
            print(f"  g={g:<6} c1={'P' if r['c1']['pass'] else 'F'} "
                  f"c2={'P' if r['c2']['pass'] else 'F'} "
                  f"c3={'P' if r['c3']['pass'] else 'F'} "
                  f"c4={'P' if r['c4']['pass'] else 'F'}  "
                  f"ALL={'PASS' if r['pass'] else 'fail'}")
        winners = [g for g, r in results if r["pass"]]
        if winners:
            print(f"\nSmallest/largest passing g in sweep: {min(winners)} / {max(winners)}")
        else:
            print("\nNo g in this sweep passes all four Diagnostic 4 checks.")
