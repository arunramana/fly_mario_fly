"""
dnp02_circuit.py — body-level DNp02 circuit: DNp02 core, its N>=60
presynaptic partners (overwhelmingly LC4 -- see SPEC_second_escape.md),
PLUS TTMn explicitly folded in so the real DNp02->TTMn synapse (21 R, 5 L,
confirmed against the weights file) is captured by the extraction. Unlike
steering_circuit.py/mdn_circuit.py, this core has a genuine downstream
target within reach, not just upstream partners -- TTMn isn't found by the
presynaptic-threshold rule (it's downstream of DNp02, not upstream), so it
is added the same way SPEC_jump.md's pooling exception adds neurons that
don't clear a threshold but are structurally load-bearing: explicitly,
stated here as a judgement call.

Same extraction/signs/weight-matrix pipeline as every other circuit in
this project. See SPEC_second_escape.md section 2.

    python dnp02_circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcns  # noqa: E402

import circuit
from query_input_pools import full_presynaptic_population

CORE_TYPES = ["DNp02"]
EXPECTED_COUNTS = {"DNp02": 2, "TTMn": 2}
DOWNSTREAM_TYPES = ["TTMn"]  # explicit exception -- see module docstring
N_THRESHOLD = 60


def core_bodies(ann: pd.DataFrame) -> pd.DataFrame:
    core = ann[ann["type"].isin(CORE_TYPES)].copy()
    counts = core["type"].value_counts().to_dict()
    for t, expected in {"DNp02": 2}.items():
        got = counts.get(t, 0)
        assert got == expected, (
            f"{t}: found {got} neurons, expected {expected}. "
            "The connectome data changed underneath us -- stop and check."
        )
    return core


def combined_presynaptic_weight(core: pd.DataFrame) -> pd.DataFrame:
    core_ids = core["bodyId"].to_numpy()
    edges = full_presynaptic_population(core_ids, "dnp02_full_presynaptic.parquet")
    per_pre = edges.groupby("body_pre", as_index=False)["weight"].sum()
    per_pre = per_pre.rename(columns={"weight": "total_weight_onto_core"})
    return per_pre.sort_values("total_weight_onto_core", ascending=False)


def build(N: int = N_THRESHOLD):
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere"])
    core = core_bodies(ann)
    per_pre = combined_presynaptic_weight(core)

    core_ids = set(core["bodyId"])
    downstream_ids = set(ann.loc[ann["type"].isin(DOWNSTREAM_TYPES), "bodyId"])
    candidates = per_pre[~per_pre["body_pre"].isin(core_ids)]
    threshold_ids = set(candidates.loc[candidates["total_weight_onto_core"] >= N, "body_pre"])

    all_ids = core_ids | threshold_ids | downstream_ids
    print(f"DNp02 circuit: N={N}")
    print(f"  core (DNp02):                        {len(core_ids)}")
    print(f"  threshold-expansion (new neurons):  {len(threshold_ids)}")
    print(f"  downstream exception (TTMn):         {len(downstream_ids)}")
    print(f"  TOTAL:                              {len(all_ids)}")

    bodies = ann[ann["bodyId"].isin(all_ids)].copy()
    bodies = bodies.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)
    bodies["in_core"] = bodies["bodyId"].isin(core_ids)
    return bodies, per_pre


def build_full(N: int = N_THRESHOLD):
    bodies, per_pre = build(N)
    counts = bodies[bodies["in_core"]]["type"].value_counts().to_dict()
    assert counts.get("DNp02", 0) == 2, f"DNp02: found {counts.get('DNp02', 0)}, expected 2"
    ttmn_count = int((bodies["type"] == "TTMn").sum())
    assert ttmn_count == 2, f"TTMn: found {ttmn_count}, expected 2 (downstream exception)"

    print("\nExtracting body-level edges over the DNp02 subgraph "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name=f"edges_dnp02_bodies_N{N}.parquet"
    )

    # Report the real DNp02->TTMn edge before it disappears into the matrix.
    side_of = bodies.set_index("bodyId")["somaSide"]
    dnp02_ids = set(bodies.loc[bodies["type"] == "DNp02", "bodyId"])
    ttmn_ids = set(bodies.loc[bodies["type"] == "TTMn", "bodyId"])
    hit = edges[edges["body_pre"].isin(dnp02_ids) & edges["body_post"].isin(ttmn_ids)]
    print("\n--- DNp02 -> TTMn (the reason TTMn is folded in explicitly) ---")
    for row in hit.itertuples():
        print(f"  DNp02[{side_of.get(row.body_pre)}] ({row.body_pre}) -> "
              f"TTMn[{side_of.get(row.body_post)}] ({row.body_post}): {row.weight} synapses")

    print("\nAssigning signs from consensus_nt...")
    signs = circuit.build_signs(bodies)

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = circuit.spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W_dnp02 (g=1): {rho1:.4f}")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
