"""
retinotopy.py -- sprint 023 built per-cell receptive fields for LC4/LPLC2
and a RAM->hex azimuth map; sprint 024 fixes the one thing 023 got wrong.

The prize, stated once, in the module docstring where it can't be missed:
this is not "which hemisphere" (that's one bit, and the jump circuit's
output is a single button -- it would be invisible). It's angular
VELOCITY. Every LC4/LPLC2 cell used to receive the identical theta/dtheta
scalar every frame -- the population had no spatial extent to move
across, so there was no velocity signal anywhere in the circuit, only
size. 019 verified real, one-hop, 100%-coverage hex input for both
populations (LC4 16.47% of total real input via Tm1/Tm2/Tm4/Tm9/Tm20;
LPLC2 5.84% via the same five types). This module turns that into
per-cell receptive-field centres, then a RAM-computed target position
that sweeps across those centres as an enemy approaches -- real motion
across a real population map.

-- 023's failure, and why it was the mapping, not the anatomy --
023 mapped d_px=0 (imminent collision) to `hex1.min()`, the extreme EDGE
of each population's real measured hex1 range. Checked directly (023's
own entry, docs/RUNS.md): that edge is the sparsest part of the real
RF-centre distribution, not its densest. Escape collapsed -- 10 commits
to 0 -- because the population was thinnest exactly when the threat was
most imminent. That is a bug in the invented convention, not evidence
retinotopy itself is behaviourally inert: a real fovea is BY DEFINITION
where cells are dense, and an edge of a range is not that, in general.

-- SCAFFOLDING, named up front, not discovered later --
Hex coordinates (019) are oblique, per-eye, and carry no degree transform
in this data -- there is no way to derive "d_px -> hex azimuth" from the
connectome itself. AZIMUTH_D_REF below is still an invented reference
distance (one genuinely new number, not derived from any synapse count,
unchanged from 023). What changes in 024: the near/foveal anchor is now
`density_mode()` -- the real peak of each population's own measured
RF-centre density (sum of per-cell Gaussians, each cell's own measured
`hex1_spread` as its bandwidth, same data 023 already computed, no new
hand-set constant) -- instead of `hex1.min()`. The far/peripheral anchor
stays `hex1.max()`, unchanged from 023 -- only the origin moved, exactly
what was specified, not a second new convention. This RELOCATES the
existing "which point is foveal" invention onto a data-derived quantity;
it does not remove the invention (an azimuth-to-hex map is still
required, and pairing an arbitrary pixel distance `AZIMUTH_D_REF` with a
hex-space distance is still a choice), and does not add a second one.
This REPLACES an existing invented map, not adds a new debt: the current
code already uses an invented convention (route enemies ahead of Mario to
one hemisphere, behind to the other, SPEC_jump.md section 2, "our own
convention, SPEC doesn't fix one") -- a binary hemisphere assignment.
Swapping one invented map (1 bit) for a finer one (a continuous position
within a real, verified receptive-field layout, now anchored at its real
density peak) is a strictly smaller invention, not a new one on top.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.feather as feather

import mcns

# Real, one-hop hex-carrying presynaptic types for LC4/LPLC2 -- 019's own
# finding, not re-derived here. Types absent from a given population's real
# input (checked in 019) are harmless no-ops if included.
HEX_TYPES = ["Tm1", "Tm2", "Tm4", "Tm9", "Tm20", "Mi1", "Mi4"]

# -- the one invented numeric scaffold, stated plainly --
# No principled reference distance exists in the data (there is no degree
# transform for hex coordinates, so "how many pixels is one hex unit" is
# not answerable from the connectome). AZIMUTH_D_REF=128px = half the NES
# screen width -- a real, already-referenced quantity in this project (the
# screen Mario/enemies are drawn on), used here only as an arbitrary but
# stated saturation point: an enemy at or beyond this distance reads as
# fully peripheral, closer than this sweeps toward the foveal extreme.
AZIMUTH_D_REF = 128.0


def _hex_lookup() -> pd.DataFrame:
    ann = feather.read_table(
        mcns.ANNOTATIONS,
        columns=["bodyId", "type", "somaSide", "assignedOlHex1", "assignedOlHex2"],
    ).to_pandas()
    return ann


def receptive_field_centers(target_type: str, bodies: pd.DataFrame) -> dict:
    """Per-cell RF centre for every real body of `target_type` (LC4 or
    LPLC2) in `bodies` (the jump circuit's own body table, load_cached's
    `bodies` -- so the returned arrays align 1:1 with Ij's own row index,
    nothing new to keep in sync). Synapse-weighted mean hex position over
    each cell's real Tm1/Tm2/Tm4/Tm9/Tm20/Mi1/Mi4 partners -- same method
    019 used for LC10a, applied here to the two populations actually
    driving the jump circuit.

    Returns {"hex1": array, "hex2": array, "hex1_spread": array, "has_rf":
    bool array}, each length len(bodies), zero/False where a body (019
    found none for LC4/LPLC2 -- 100% coverage both) has no real
    hex-carrying input at all. `hex2` is returned (and used by
    `brain_panel`-style diagnostics/logging) but not by `tuning_weights`
    -- see that function's docstring.
    """
    ann = _hex_lookup()
    hex_lookup = ann.set_index("bodyId")[["assignedOlHex1", "assignedOlHex2"]]
    id2type = ann.set_index("bodyId")["type"]

    # Reuses 019's own cached whole-connectome presynaptic population for
    # this type (`{type}_full_presynaptic.parquet`) rather than a fresh
    # body_subgraph scan -- same data, already on disk, no new streaming
    # pass over 152M edges needed.
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
    """sprint 024: the real peak of a population's own measured hex1
    RF-centre density -- sum of one Gaussian per real cell (mean=that
    cell's own hex1, bandwidth=that cell's own measured hex1_spread, the
    SAME arrays `receptive_field_centers` already returns, no new
    constant), evaluated on a grid spanning the population's own real
    [min, max] and reporting the argmax. This is what 023 should have
    anchored "foveal" to and didn't -- checked directly in 023's own
    writeup that `hex1.min()` (023's actual choice) sits at the sparsest
    part of this same density curve, not its peak."""
    lo, hi = hex1.min(), hex1.max()
    grid = np.linspace(lo, hi, grid_n)
    density = np.zeros_like(grid)
    for centre, spread in zip(hex1, hex1_spread):
        density += np.exp(-0.5 * ((grid - centre) / spread) ** 2) / spread
    return float(grid[np.argmax(density)])


def azimuth_target(d_px: float, hex1_origin: float, hex1_far: float, hex2_mid: float,
                    d_ref: float = AZIMUTH_D_REF) -> float:
    """The RAM -> hex-azimuth map, hex1 ONLY. `d_px` is the SAME signed
    pixel distance enemy_thetas() already computes (only its magnitude
    matters here -- side/hemisphere routing is unchanged, handled the
    same way it always has been). d_px=0 (about to collide) maps to
    `hex1_origin` -- sprint 024: the population's real density mode
    (`density_mode`, above), replacing 023's `hex1.min()`, the fix this
    sprint exists to test. d_px>=d_ref maps to `hex1_far`, still
    `hex1.max()` -- UNCHANGED from 023, since the spec for this sprint is
    "move the origin," not "invent a second new convention" for the far
    anchor too. `hex2_mid` is accepted and ignored -- kept in the
    signature as a record of a first version that also fixed a target
    hex2 and penalised every cell's distance from it. Found, by running
    it, to be the wrong call: this game has no elevation signal, and
    fixing an arbitrary target elevation doesn't stay neutral about that
    missing axis, it actively SUPPRESSES every real cell whose own
    measured elevation differs from the fixed point -- which is most of
    them, since real elevation coverage spans the population's full
    range. The honest way to be agnostic about an axis you can't drive is
    to not score distance on it at all, not to invent a fixed value and
    penalise deviation from it."""
    frac = np.clip(abs(d_px) / d_ref, 0.0, 1.0)
    return hex1_origin + frac * (hex1_far - hex1_origin)


def tuning_weights(target_hex1: float, rf: dict) -> np.ndarray:
    """Gaussian per-cell weight over hex1 (azimuth) ONLY -- see
    azimuth_target's docstring for why hex2 doesn't enter this at all.
    Bandwidth = that cell's own measured RF spread (data-derived, not a
    hand-set constant -- avoids adding yet another invented number on top
    of AZIMUTH_D_REF), computed over its real hex1 spread specifically,
    not the full 2D spread (which would still be contaminated by hex2
    variability this weight no longer scores)."""
    d1 = rf["hex1"] - target_hex1
    return np.exp(-0.5 * (d1 / rf["hex1_spread"]) ** 2)
