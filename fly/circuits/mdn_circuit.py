"""
mdn_circuit.py — body-level MDN circuit: MDN (Moonwalker Descending
Neurons, backward walking) core plus every presynaptic partner with >=60
synapses onto the 4 MDN bodies.

Built with circuit.py's pipeline. See SPEC_habituation.md section 2. No
direct synapse from DNp01 or GFC1-4 onto
MDN in this connectome (checked) -- same situation DNp09 was in (007), so
MDN's drive is an external current (MDN_DRIVE, run_steering.py), not
something wired in from the escape circuit itself.

    python mdn_circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import mcns  # noqa: E402

from fly.connectome import circuit
from fly.connectome.query_input_pools import full_presynaptic_population

CORE_TYPES = ["MDN"]
EXPECTED_COUNTS = {"MDN": 4}
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
    """Per presynaptic body: total synapses onto the 4 MDN bodies, whole
    connectome -- same N=60 threshold rule as every other population here."""
    core_ids = core["bodyId"].to_numpy()
    edges = full_presynaptic_population(core_ids, "mdn_full_presynaptic.parquet")
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
    print(f"MDN circuit: N={N}")
    print(f"  core (MDN):                          {len(core_ids)}")
    print(f"  threshold-expansion (new neurons):  {len(threshold_ids)}")
    print(f"  TOTAL:                              {len(all_ids)}")

    bodies = ann[ann["bodyId"].isin(all_ids)].copy()
    bodies = bodies.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)
    bodies["in_core"] = bodies["bodyId"].isin(core_ids)
    return bodies, per_pre


def build_full(N: int = N_THRESHOLD):
    """Full pipeline: extract, sign, weight-matrix. Mirrors
    steering_circuit.build_full's shape but for the MDN core."""
    bodies, per_pre = build(N)
    core = bodies[bodies["in_core"]]
    counts = core["type"].value_counts().to_dict()
    for t, expected in EXPECTED_COUNTS.items():
        got = counts.get(t, 0)
        assert got == expected, f"{t}: found {got}, expected {expected} (core unaffected by expansion)"

    print("\nExtracting body-level edges over the MDN subgraph "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name=f"edges_mdn_bodies_N{N}.parquet"
    )

    print("\nAssigning signs from consensus_nt...")
    signs = circuit.build_signs(bodies)

    sign_of_body = signs.reindex(bodies["bodyId"]).to_numpy()
    print("  sign by type (MDN core):")
    for t in CORE_TYPES:
        sub = sign_of_body[bodies["type"].to_numpy() == t]
        print(f"    {t:8s} +1: {int((sub > 0).sum()):3d}  "
              f"-1: {int((sub < 0).sum()):3d}  0: {int((sub == 0).sum()):3d}")

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = circuit.spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W_mdn (g=1): {rho1:.4f}")

    print("\n--- E/I balance of the MDN subgraph (by neuron count) ---")
    n_exc = int((sign_of_body > 0).sum())
    n_inh = int((sign_of_body < 0).sum())
    n_zero = int((sign_of_body == 0).sum())
    print(f"  excitatory: {n_exc}  inhibitory: {n_inh}  unsigned: {n_zero}  "
          f"(of {len(bodies)} total)")

    print("\n--- input coverage for MDN ---")
    for t in CORE_TYPES:
        frac = diag.loc[diag["type"] == t, "coverage_frac"]
        print(f"  {t:8s} mean coverage: {frac.mean()*100:.1f}%  "
              f"(min {frac.min()*100:.1f}%, max {frac.max()*100:.1f}%)")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
