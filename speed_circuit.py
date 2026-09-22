"""
speed_circuit.py — SPEC_terrain.md section 3: DNp09 (forward walking, 2
neurons) plus every presynaptic partner with >=60 synapses onto DNp01...
onto DNp09. Checked directly against the weights file: DNa01/DNa02 (the
steering circuit) have NO direct synapse onto DNp09, so this needs its own
small subgraph rather than reusing steering's output -- 23 partners, 25
neurons total.

Same extraction/signs/weight-matrix pipeline as circuit.py/
steering_circuit.py. Does not modify either.

    python speed_circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcns  # noqa: E402

import circuit
from query_input_pools import full_presynaptic_population

CORE_TYPES = ["DNp09"]
EXPECTED_COUNTS = {"DNp09": 2}
N_THRESHOLD = 60


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


def combined_presynaptic_weight(core: pd.DataFrame) -> pd.DataFrame:
    core_ids = core["bodyId"].to_numpy()
    edges = full_presynaptic_population(core_ids, "dnp09_full_presynaptic.parquet")
    per_pre = edges.groupby("body_pre", as_index=False)["weight"].sum()
    per_pre = per_pre.rename(columns={"weight": "total_weight_onto_core"})
    return per_pre.sort_values("total_weight_onto_core", ascending=False)


def build(N: int = N_THRESHOLD):
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere"])
    core = core_bodies(ann)
    per_pre = combined_presynaptic_weight(core)

    core_ids = set(core["bodyId"])
    candidates = per_pre[~per_pre["body_pre"].isin(core_ids)]
    threshold_ids = set(candidates.loc[candidates["total_weight_onto_core"] >= N, "body_pre"])

    all_ids = core_ids | threshold_ids
    print(f"speed circuit: N={N}")
    print(f"  core (DNp09):                       {len(core_ids)}")
    print(f"  threshold-expansion (new neurons):  {len(threshold_ids)}")
    print(f"  TOTAL:                              {len(all_ids)}")

    bodies = ann[ann["bodyId"].isin(all_ids)].copy()
    bodies = bodies.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)
    bodies["in_core"] = bodies["bodyId"].isin(core_ids)
    return bodies, per_pre


def build_full(N: int = N_THRESHOLD):
    bodies, per_pre = build(N)
    core = bodies[bodies["in_core"]]
    counts = core["type"].value_counts().to_dict()
    for t, expected in EXPECTED_COUNTS.items():
        got = counts.get(t, 0)
        assert got == expected, f"{t}: found {got}, expected {expected} (core unaffected by expansion)"

    print("\nExtracting body-level edges over the speed subgraph "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name=f"edges_speed_bodies_N{N}.parquet"
    )

    print("\nAssigning signs from consensus_nt...")
    signs = circuit.build_signs(bodies)

    sign_of_body = signs.reindex(bodies["bodyId"]).to_numpy()
    print("  sign by type (speed core types):")
    for t in CORE_TYPES:
        sub = sign_of_body[bodies["type"].to_numpy() == t]
        print(f"    {t:8s} +1: {int((sub > 0).sum()):3d}  "
              f"-1: {int((sub < 0).sum()):3d}  0: {int((sub == 0).sum()):3d}")

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = circuit.spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W_speed (g=1): {rho1:.4f}")

    print("\n--- E/I balance of the speed subgraph (by neuron count) ---")
    n_exc = int((sign_of_body > 0).sum())
    n_inh = int((sign_of_body < 0).sum())
    n_zero = int((sign_of_body == 0).sum())
    print(f"  excitatory: {n_exc}  inhibitory: {n_inh}  unsigned: {n_zero}  "
          f"(of {len(bodies)} total)")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
