"""
commitment_report.py -- sprint 023's own decisive measurement, factored out
so the same code runs identically on the before/after telemetry. Sprint
024 extended the correlation check to LPLC2 as well as LC4, after finding
the LC4-only version was confounded (see below).

Two questions, both readable straight from a run_steering.py telemetry
DataFrame (023 added `dtheta`/`d_px`/`frames_to_contact` alongside the
existing `theta`/`lc4`/`lplc2`/`pathway_fired`):

1. Commitment timing: for each real escape-jump trigger (`pathway_fired`
   non-empty, sprint 012's own attribution field), `frames_to_contact` is
   the SAME estimate the live run already computes and prints (closing
   speed from `d_history`, an existing 10-frame window, times `d_px` at
   the commit frame) -- not re-derived here, just read back from telemetry.
2. corr(pop, theta) vs corr(pop, dtheta), for BOTH LC4 and LPLC2 --
   003/019's own read of LC4's corr(theta)=0.50 was "LC4 is velocity-
   tuned"; it can't have been, since nothing moved across the population
   before 023. 024 found (docs/RUNS.md) that this comparison, done on
   LC4 alone, is confounded: LC4's own scalar drive is `abs(dtheta)`, not
   `theta`, since long before 023 (`Ij[LC4_mask] = abs(dtheta)` --
   unchanged by any retinotopy sprint) -- so corr(LC4,dtheta) > corr(
   LC4,theta) is mechanically guaranteed regardless of whether retinotopy
   does anything at all. LPLC2's own scalar drive is `theta`, the mirror
   case -- reporting both pairs, for both populations, is what actually
   tests for a population-level (not just scalar-input) motion signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def find_commitments(tel: pd.DataFrame) -> list[dict]:
    fired = tel["pathway_fired"].fillna("").to_numpy()
    idx = np.where(fired != "")[0]
    events = []
    for i in idx:
        ftc = tel["frames_to_contact"].iloc[i]
        d_commit = tel["d_px"].iloc[i]
        events.append({
            "frame": int(tel["frame"].iloc[i]),
            "pathway": fired[i],
            "d_px_commit": float(d_commit) if pd.notna(d_commit) else None,
            "frames_to_contact": float(ftc) if pd.notna(ftc) else None,
        })
    return events


def safe_corr(a, b):
    # constant-column guard: a run with ~zero variance in a population or
    # theta (e.g. no enemy ever seen) makes corrcoef return nan, not an error
    if np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def correlation_signature(tel: pd.DataFrame) -> dict:
    theta = tel["theta"].to_numpy()
    dtheta_abs = tel["dtheta"].abs().to_numpy()
    out = {}
    for pop in ("lc4", "lplc2"):
        v = tel[pop].to_numpy()
        out[f"corr_{pop}_theta"] = safe_corr(v, theta)
        out[f"corr_{pop}_dtheta"] = safe_corr(v, dtheta_abs)
    return out


def report(tel: pd.DataFrame, label: str) -> dict:
    events = find_commitments(tel)
    corr = correlation_signature(tel)
    ftc = [e["frames_to_contact"] for e in events if e["frames_to_contact"] is not None]
    print(f"\n--- {label} ---")
    print(f"escape commitments: {len(events)}")
    for e in events:
        print(f"  frame {e['frame']}: pathway={e['pathway']} d_px={e['d_px_commit']} "
              f"frames_to_contact={e['frames_to_contact']}")
    if ftc:
        print(f"  median frames_to_contact at commit: {np.median(ftc):.1f}  mean: {np.mean(ftc):.1f}")
    for pop in ("lc4", "lplc2"):
        print(f"  corr({pop.upper()}, theta)  = {corr[f'corr_{pop}_theta']:.4f}   "
              f"corr({pop.upper()}, dtheta) = {corr[f'corr_{pop}_dtheta']:.4f}")
    return {"events": events, "corr": corr,
            "median_frames_to_contact": float(np.median(ftc)) if ftc else None}
