# What this file does, in plain English:
# An experimental way to feed Mario's view to the looming detectors so each
# cell responds to its own patch of the visual field, placed using where
# each cell gets its eye input in the wiring diagram. The project's run log
# records that it broke the escape jump, so it is off by default and kept
# as a record of that result.
"""
retinotopy.py -- per-cell receptive fields for LC4/LPLC2 and a RAM -> hex
azimuth map, so an approaching enemy sweeps across the real population
instead of every cell receiving the same theta/dtheta scalar.

The point is angular velocity, not "which hemisphere": with a uniform
broadcast the population has no spatial extent to move across, so the
circuit only ever sees size. Both populations have one-hop, 100%-coverage
hex input (LC4 16.47% of total input via Tm1/Tm2/Tm4/Tm9/Tm20; LPLC2
5.84% via the same five types).

Closed negative result (docs/RUNS.md 023-024): even with the fovea at the
real RF density peak, per-cell weighting starves DNp01/TTMn of drive and
escape collapses. `retinotopic=False` is the permanent default; this
module is kept as a working record of that result.

Hex coordinates are oblique, per-eye and have no degree transform in this
data, so the pixel -> hex map cannot come from the connectome. Its one
invented number is AZIMUTH_D_REF; the foveal anchor is data-derived
(`density_mode`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.feather as feather

import mcns

# One-hop hex-carrying presynaptic types for LC4/LPLC2 (docs/RUNS.md 019).
# Types absent from a population's input are harmless no-ops.
HEX_TYPES = ["Tm1", "Tm2", "Tm4", "Tm9", "Tm20", "Mi1", "Mi4"]

# Invented: half the NES screen width. An enemy at or beyond this distance
# reads as fully peripheral; closer sweeps toward the fovea.
AZIMUTH_D_REF = 128.0


def _hex_lookup() -> pd.DataFrame:
    ann = feather.read_table(
        mcns.ANNOTATIONS,
        columns=["bodyId", "type", "somaSide", "assignedOlHex1", "assignedOlHex2"],
    ).to_pandas()
    return ann


def receptive_field_centers(target_type: str, bodies: pd.DataFrame) -> dict:
    """Per-cell RF centre for every body of `target_type` (LC4 or LPLC2) in
    the jump circuit's `bodies` table, so the arrays align 1:1 with its
    rows. Synapse-weighted mean hex position over each cell's hex-carrying
    partners.

    Returns {"hex1", "hex2", "hex1_spread", "has_rf"}, each len(bodies),
    zero/False for a body with no hex input (none, for LC4/LPLC2). `hex2`
    is informational; `tuning_weights` scores hex1 only.
    """
    ann = _hex_lookup()
    hex_lookup = ann.set_index("bodyId")[["assignedOlHex1", "assignedOlHex2"]]
    id2type = ann.set_index("bodyId")["type"]

    # The cached whole-connectome presynaptic population for this type,
    # instead of another streaming pass over 152M edges.
    edges = pd.read_parquet(mcns.DERIVED / f"{target_type.lower()}_full_presynaptic.parquet")
    edges = edges.copy()
    edges["pre_type"] = edges["body_pre"].map(id2type)
    hexin = edges[edges["pre_type"].isin(HEX_TYPES)].copy()
    hexin = hexin.merge(hex_lookup, left_on="body_pre", right_index=True, how="left")
    hexin = hexin.dropna(subset=["assignedOlHex1", "assignedOlHex2"])

    n = len(bodies)
    hex1 = np.zeros(n)
    hex2 = np.zeros(n)
    hex1_spread = np.full(n, 3.0)  # fallback bandwidth for the (verified-empty) no-coverage case
    has_rf = np.zeros(n, dtype=bool)

    id_to_row = {bid: i for i, bid in enumerate(bodies["bodyId"].to_numpy())}
    for post_id, g in hexin.groupby("body_post"):
        row = id_to_row.get(post_id)
        if row is None:
            continue
        w = g["weight"].to_numpy().astype(float)
        h1 = g["assignedOlHex1"].to_numpy()
        h2 = g["assignedOlHex2"].to_numpy()
        m1 = np.average(h1, weights=w)
        m2 = np.average(h2, weights=w)
        s1 = np.sqrt(np.average((h1 - m1) ** 2, weights=w))
        hex1[row] = m1
        hex2[row] = m2
        hex1_spread[row] = max(s1, 0.5)  # floor -- a single-partner cell has zero measured
        has_rf[row] = True               # spread, which would make its tuning curve a delta function

    return {"hex1": hex1, "hex2": hex2, "hex1_spread": hex1_spread, "has_rf": has_rf}


def density_mode(hex1: np.ndarray, hex1_spread: np.ndarray, grid_n: int = 2000) -> float:
    """Peak of the population's hex1 RF-centre density: one Gaussian per
    cell (its own hex1 and measured spread), argmax over [min, max]. A
    fovea is where cells are dense; the edge of the range (`hex1.min()`)
    is the sparsest part of this curve."""
    lo, hi = hex1.min(), hex1.max()
    grid = np.linspace(lo, hi, grid_n)
    density = np.zeros_like(grid)
    for centre, spread in zip(hex1, hex1_spread):
        density += np.exp(-0.5 * ((grid - centre) / spread) ** 2) / spread
    return float(grid[np.argmax(density)])


def azimuth_target(d_px: float, hex1_origin: float, hex1_far: float,
                    d_ref: float = AZIMUTH_D_REF) -> float:
    """RAM -> hex1 azimuth. `d_px` is enemy_thetas()'s signed distance;
    only its magnitude matters (hemisphere routing is unchanged). d_px=0
    maps to `hex1_origin` (the density mode), d_px >= d_ref to `hex1_far`
    (`hex1.max()`).

    No hex2 (elevation) target: the game has no elevation signal, and
    fixing an arbitrary one would suppress every cell whose real elevation
    differs from it."""
    frac = np.clip(abs(d_px) / d_ref, 0.0, 1.0)
    return hex1_origin + frac * (hex1_far - hex1_origin)


def tuning_weights(target_hex1: float, rf: dict) -> np.ndarray:
    """Gaussian per-cell weight over hex1 only, bandwidth = each cell's own
    measured hex1 spread (data-derived, not another hand-set constant)."""
    d1 = rf["hex1"] - target_hex1
    return np.exp(-0.5 * (d1 / rf["hex1_spread"]) ** 2)
