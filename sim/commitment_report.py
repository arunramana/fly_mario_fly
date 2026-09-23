# What this file does, in plain English:
# Reads the per-frame log (telemetry) of a finished run_steering.py game.
# It lists each moment the fly's escape reflex committed to a jump, with how
# many frames the enemy was from reaching Mario then, and measures how
# closely two threat-detecting cell groups tracked the enemy's apparent size
# versus how fast that size changed. Used by run_steering.py runs 023/024.
"""
commitment_report.py -- the retinotopy measurement (docs/RUNS.md 023-024),
read from a run_steering.py telemetry DataFrame:

1. Commitment timing: for each escape-jump trigger (`pathway_fired`
   non-empty), the `frames_to_contact` the live run already computed.
2. corr(pop, theta) vs corr(pop, |dtheta|) for BOTH LC4 and LPLC2. LC4 is
   driven by |dtheta| and LPLC2 by theta, so either pair alone is
   mechanically biased toward its own input; only both together test for
   a population-level motion signal.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


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
    log.info(f"\n--- {label} ---")
    log.info(f"escape commitments: {len(events)}")
    for e in events:
        log.info(f"  frame {e['frame']}: pathway={e['pathway']} d_px={e['d_px_commit']} "
                 f"frames_to_contact={e['frames_to_contact']}")
    if ftc:
        log.info(f"  median frames_to_contact at commit: {np.median(ftc):.1f}  mean: {np.mean(ftc):.1f}")
    for pop in ("lc4", "lplc2"):
        log.info(f"  corr({pop.upper()}, theta)  = {corr[f'corr_{pop}_theta']:.4f}   "
                 f"corr({pop.upper()}, dtheta) = {corr[f'corr_{pop}_dtheta']:.4f}")
    return {"events": events, "corr": corr,
            "median_frames_to_contact": float(np.median(ftc)) if ftc else None}
