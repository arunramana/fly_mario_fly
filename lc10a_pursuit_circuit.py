"""
lc10a_pursuit_circuit.py -- sprint 019: the real, traced LC10a -> AOTU ->
TuBu -> ring (ER/ExR) -> PFL3 -> DNa02 pathway, body-level.

Not an N>=60 threshold expansion around a core (SPEC_jump section 1b's
rule, reused by steering_circuit.py/dnp02_circuit.py's own threshold
partners) -- LC10a's own top real partners by raw synapse weight are
NOT the spatial relay (018/019's own finding: AOTU008/041/019 etc. don't
feed TuBu; TuBu's real input is dominated by an unrelated MeTu stream).
A blind threshold from LC10a would pull in the wrong neurons and miss
the real, if thin, spatial channel entirely. This is a NAMED-population
extraction instead, same category as takeoff_circuit.py's "DNp01 core +
GFC1-4 + DLMn, folded in explicitly to capture the real downstream edge"
-- the five populations sprint 018/019 actually traced by real,
heaviest-edge queries, nothing else:

    LC10a (275)  ->  TuBu (156, all 10 subtypes)  ->  ring ER/ExR (296,
    29 subtypes)  ->  PFL3 (24)  ->  DNa02 (2, the SAME two bodies
    steering_circuit.py's own core uses)

753 bodies total. Real edges/signs/weight matrix via the same reused
helpers every other circuit in this project uses (mcns.body_subgraph,
circuit.build_signs, circuit.build_weight_matrix) -- nothing new to
write there.

    python lc10a_pursuit_circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcns  # noqa: E402

import circuit

# The traced chain's real populations, sprint 018 (hop-by-hop synapse
# counts) + sprint 019 (the decisive tiling test, LC10a's own real
# hex-carrying one-hop input). TuBu/ring lists are every subtype found
# with a nonzero real edge in that trace, not hand-picked "top N".
TUBU_TYPES = [f"TuBu{n:02d}" for n in range(1, 11)]
RING_TYPES = [
    "ExR1", "ExR2", "ExR3", "ExR5",
    "ER1_a", "ER1_b", "ER1_c", "ER2_a", "ER2_b", "ER2_c", "ER2_d",
    "ER3a_a", "ER3a_b", "ER3a_c", "ER3a_d",
    "ER3d_a", "ER3d_b", "ER3d_c", "ER3d_d", "ER3d_e",
    "ER3m", "ER3p_a", "ER3p_b", "ER3w_a", "ER3w_b", "ER3w_c",
    "ER4d", "ER4m", "ER5", "ER6",
]
CORE_TYPES = ["LC10a"] + TUBU_TYPES + RING_TYPES + ["PFL3", "DNa02"]
EXPECTED_COUNTS = {"LC10a": 275, "PFL3": 24, "DNa02": 2}
CACHE_NAME = "edges_lc10a_pursuit_bodies.parquet"


def core_bodies(ann: pd.DataFrame) -> pd.DataFrame:
    core = ann[ann["type"].isin(CORE_TYPES)].copy()
    for t, expected in EXPECTED_COUNTS.items():
        got = int((core["type"] == t).sum())
        assert got == expected, (
            f"{t}: found {got} neurons, expected {expected}. "
            "The connectome data changed underneath us -- stop and check."
        )
    return core.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)


def build_full():
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere"])
    bodies = core_bodies(ann)
    print(f"LC10a pursuit circuit -- named-population extraction, not N-threshold:")
    for t in ["LC10a"]:
        print(f"  {t}: {(bodies['type']==t).sum()}")
    print(f"  TuBu (10 subtypes): {bodies['type'].isin(TUBU_TYPES).sum()}")
    print(f"  ring ER/ExR (29 subtypes): {bodies['type'].isin(RING_TYPES).sum()}")
    for t in ["PFL3", "DNa02"]:
        print(f"  {t}: {(bodies['type']==t).sum()}")
    print(f"  TOTAL: {len(bodies)}")

    print("\nExtracting body-level edges over the pursuit subgraph "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(bodies["bodyId"], cache_name=CACHE_NAME)

    print("\nAssigning signs from consensus_nt...")
    signs = circuit.build_signs(bodies)

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = circuit.spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W_pursuit (g=1): {rho1:.4f}")

    print("\n--- input coverage (in-subgraph / real total) for the chain's endpoints ---")
    for t in ["LC10a", "PFL3", "DNa02"]:
        frac = diag.loc[diag["type"] == t, "coverage_frac"]
        print(f"  {t:8s} mean coverage: {frac.mean()*100:.1f}%  "
              f"(min {frac.min()*100:.1f}%, max {frac.max()*100:.1f}%)")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
