"""
commitment_report.py -- sprint 023's own decisive measurement, factored out
so the same code runs identically on the before/after telemetry.

Two questions, both readable straight from a run_steering.py telemetry
DataFrame (023 added `dtheta`/`d_px`/`frames_to_contact` alongside the
existing `theta`/`lc4`/`pathway_fired`):

1. Commitment timing: for each real escape-jump trigger (`pathway_fired`
   non-empty, sprint 012's own attribution field), `frames_to_contact` is
   the SAME estimate the live run already computes and prints (closing
   speed from `d_history`, an existing 10-frame window, times `d_px` at
   the commit frame) -- not re-derived here, just read back from telemetry.
2. corr(LC4_mean, theta) vs corr(LC4_mean, dtheta) over the whole run --
   003/019's own read of the first was "LC4 is velocity-tuned"; it can't
   have been, since nothing moved across the population before this
   sprint. If retinotopy makes LC4 genuinely velocity-tuned, the second
   correlation should now exceed the first.
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


def correlation_signature(tel: pd.DataFrame) -> dict:
    lc4 = tel["lc4"].to_numpy()
    theta = tel["theta"].to_numpy()
    dtheta_abs = tel["dtheta"].abs().to_numpy()

    def safe_corr(a, b):
        # constant-column guard: a run with ~zero variance in lc4 or theta
        # (e.g. no enemy ever seen) makes corrcoef return nan, not an error
        if np.std(a) < 1e-12 or np.std(b) < 1e-12:
            return float("nan")
        return float(np.corrcoef(a, b)[0, 1])

    return {
        "corr_lc4_theta": safe_corr(lc4, theta),
        "corr_lc4_dtheta": safe_corr(lc4, dtheta_abs),
    }


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
    print(f"  corr(LC4_mean, theta)  = {corr['corr_lc4_theta']:.4f}")
    print(f"  corr(LC4_mean, dtheta) = {corr['corr_lc4_dtheta']:.4f}")
    return {"events": events, "corr": corr,
            "median_frames_to_contact": float(np.median(ftc)) if ftc else None}
