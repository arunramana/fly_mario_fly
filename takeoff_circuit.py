"""
takeoff_circuit.py — SPEC_terrain.md section 2: DNp01's own graded escape,
extended to recruit the wing motor neurons.

Core = DNp01 (2, same 2 bodies as the jump circuit) + GFC1-4 (34: the "Giant
Fiber Circuit" interneurons, named in this connectome, downstream of DNp01)
+ DLMn (10: 8 in type "DLMn c-f", 2 in type "DLMn a, b" -- wing downstroke
motor neurons). Verified directly against the weights file before writing
this: DNp01 has ZERO direct synapses onto DLMn, but real, substantial
synapses onto GFC1-4 (144/112/107/97 synapses respectively), and GFC1-4
synapse onto DLMn with 80 real edges. This is the documented disynaptic
jump-to-flight relay in the Giant Fiber literature (GF -> PSI-class
interneuron -> DLMn) -- not invented for this sprint, it's why GFC1-4 exist
as a named class in this connectome at all.

Same extraction/signs/weight-matrix pipeline as circuit.py and
steering_circuit.py -- does not modify circuit.py, reuses its
build_signs/build_weight_matrix/spectral_radius, which are generic over any
(bodies, edges, signs).

    python takeoff_circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcns  # noqa: E402

import circuit

CORE_TYPES = ["DNp01", "GFC1", "GFC2", "GFC3", "GFC4", "DLMn c-f", "DLMn a, b"]
EXPECTED_COUNTS = {
    "DNp01": 2, "GFC1": 3, "GFC2": 10, "GFC3": 13, "GFC4": 8,
    "DLMn c-f": 8, "DLMn a, b": 2,
}
DLMN_TYPES = ["DLMn c-f", "DLMn a, b"]


def core_bodies(ann: pd.DataFrame) -> pd.DataFrame:
    core = ann[ann["type"].isin(CORE_TYPES)].copy()
    counts = core["type"].value_counts().to_dict()
    for t, expected in EXPECTED_COUNTS.items():
        got = counts.get(t, 0)
        assert got == expected, (
            f"{t}: found {got} neurons, expected {expected}. "
            "The connectome data changed underneath us -- stop and check."
        )
    return core


def build_full():
    """No threshold expansion here -- unlike circuit.py/steering_circuit.py,
    this is a fixed, small, fully-named relay (DNp01 -> GFC1-4 -> DLMn), not
    a sign-agnostic threshold subgraph. 49 neurons total."""
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere"])
    bodies = core_bodies(ann).sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)
    print(f"takeoff circuit: {len(bodies)} neurons (fixed relay, no threshold expansion)")
    print(bodies["type"].value_counts().to_string())

    print("\nExtracting body-level edges over the takeoff relay "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name="edges_takeoff_bodies.parquet"
    )

    n_dnp01_to_dlmn = len(edges[edges["body_pre"].isin(
        ann.loc[ann["type"] == "DNp01", "bodyId"]) & edges["body_post"].isin(
        ann.loc[ann["type"].isin(DLMN_TYPES), "bodyId"])])
    print(f"\nDNp01 -> DLMn DIRECT edges in this subgraph: {n_dnp01_to_dlmn} "
          "(expected 0 -- the relay is disynaptic through GFC1-4)")
    assert n_dnp01_to_dlmn == 0, "Direct DNp01->DLMn edge appeared -- data changed, re-check the relay claim."

    print("\nAssigning signs from consensus_nt...")
    signs = circuit.build_signs(bodies)

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = circuit.spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W_takeoff (g=1): {rho1:.4f}")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
