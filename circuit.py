"""
circuit.py — body-level escape circuit: extraction, signs, weight matrix.

313 neurons (LC4 126, LPLC2 185, DNp01 2) plus TTMn (2), all at body-id
resolution rather than the type-level summary in escape_circuit.py. This is
what actually gets simulated — a type-level matrix has no individual neurons
to run a dynamical system over.

    python circuit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mcns  # noqa: E402

TYPES = ["LC4", "LPLC2", "DNp01", "TTMn"]
EXPECTED_COUNTS = {"LC4": 126, "LPLC2": 185, "DNp01": 2, "TTMn": 2}

# The four verified type-level connections from SPEC_jump.md section 1.
# Body-level extraction must roll up to exactly these, or the data changed
# underneath us.
EXPECTED_TYPE_EDGES = {
    ("LC4", "DNp01"): (6362, 126),
    ("LPLC2", "DNp01"): (4862, 185),
    ("LC4", "LC4"): (18392, 5334),
    ("LPLC2", "LPLC2"): (46178, 13434),
}

NT_SIGN = {
    "acetylcholine": 1.0,
    "dopamine": 1.0,
    "gaba": -1.0,
    "glutamate": -1.0,
}


def load_bodies() -> pd.DataFrame:
    """The 315 neurons of interest, with type, hemisphere and soma neuromere."""
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere"])
    bodies = ann[ann["type"].isin(TYPES)].copy()
    bodies = bodies.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)

    counts = bodies["type"].value_counts().to_dict()
    for t, expected in EXPECTED_COUNTS.items():
        got = counts.get(t, 0)
        assert got == expected, (
            f"{t}: found {got} neurons, expected {expected}. "
            "The connectome data changed underneath us — stop and check."
        )
    return bodies


def extract_edges(bodies: pd.DataFrame):
    """Body-level edges among the 315 neurons, plus each neuron's real total
    input across the whole connectome (for the coverage-fraction log)."""
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name="edges_circuit_bodies.parquet"
    )
    return edges, total_input


def assert_type_rollup(edges: pd.DataFrame, bodies: pd.DataFrame):
    """The body-level edges must sum back up to the verified type-level table."""
    type_of = bodies.set_index("bodyId")["type"]
    e = edges.copy()
    e["pre_type"] = e["body_pre"].map(type_of)
    e["post_type"] = e["body_post"].map(type_of)
    rollup = e.groupby(["pre_type", "post_type"])[["weight", "n_edges"]].sum()

    for (pre, post), (exp_w, exp_n) in EXPECTED_TYPE_EDGES.items():
        got_w, got_n = rollup.loc[(pre, post), "weight"], rollup.loc[(pre, post), "n_edges"]
        assert (got_w, got_n) == (exp_w, exp_n), (
            f"{pre}->{post}: body-level rollup gives {got_w}/{got_n}, "
            f"expected {exp_w}/{exp_n}. Data changed or extraction bug."
        )
    print("  body-level edges roll up to the verified type-level table. OK.")
    return rollup


def report_dnp01_to_ttmn(edges: pd.DataFrame, bodies: pd.DataFrame):
    """SPEC flags this as unverified: does the Giant Fiber actually reach the
    jump muscle motor neuron directly? Report what the data says, per side."""
    side_of = bodies.set_index("bodyId")["somaSide"]
    gf_ids = set(bodies.loc[bodies["type"] == "DNp01", "bodyId"])
    ttmn_ids = set(bodies.loc[bodies["type"] == "TTMn", "bodyId"])

    hit = edges[edges["body_pre"].isin(gf_ids) & edges["body_post"].isin(ttmn_ids)]
    print("\n--- DNp01 -> TTMn (unverified in SPEC, checking now) ---")
    if hit.empty:
        print("  NOT FOUND. Zero direct synapses in the weights file at this "
              "confidence threshold. The spec's looming->...->TTMn->press A "
              "chain assumes an edge that isn't here — flag this before "
              "wiring the output stage.")
    else:
        for _, row in hit.iterrows():
            pre_side = side_of.get(row.body_pre, "?")
            post_side = side_of.get(row.body_post, "?")
            print(f"  DNp01[{pre_side}] ({row.body_pre}) -> "
                  f"TTMn[{post_side}] ({row.body_post}): "
                  f"{int(row.weight)} synapses")
        crossed = hit.apply(
            lambda r: side_of.get(r.body_pre) != side_of.get(r.body_post), axis=1
        )
        if crossed.any() and crossed.all():
            print("  Every connection crosses the midline (contralateral) — "
                  "consistent with the fly Giant Fiber axon crossing before "
                  "synapsing on TTMn.")
        elif not crossed.any():
            print("  Every connection is ipsilateral.")
        else:
            print("  Mixed ipsi/contralateral — check by hand before assuming "
                  "a wiring rule.")
    return hit


def build_signs(bodies: pd.DataFrame) -> pd.Series:
    """Dale's law: one sign per presynaptic body, from consensus_nt."""
    nt = mcns.load_neurotransmitters()
    nt = nt.rename(columns={"body": "bodyId"})[["bodyId", "consensus_nt"]]
    merged = bodies[["bodyId", "type"]].merge(nt, on="bodyId", how="left")

    sign_val = merged["consensus_nt"].str.lower().map(NT_SIGN)
    n_unknown = sign_val.isna().sum()
    if n_unknown:
        unknown_nts = merged.loc[sign_val.isna(), "consensus_nt"].value_counts()
        print(f"  {n_unknown} of {len(merged)} neurons have no +/- sign "
              f"(unmapped or missing consensus_nt) -> sign 0, dropped as sources:")
        print(f"    {unknown_nts.to_dict()}")
    sign_val = sign_val.fillna(0.0)

    print("  sign by type:")
    for t in TYPES:
        sub = sign_val[merged["type"] == t]
        print(f"    {t:8s} +1: {int((sub > 0).sum()):3d}  "
              f"-1: {int((sub < 0).sum()):3d}  0: {int((sub == 0).sum()):3d}")

    return pd.Series(sign_val.values, index=merged["bodyId"].values, name="sign")


def build_weight_matrix(bodies: pd.DataFrame, edges: pd.DataFrame,
                         total_input: pd.Series, signs: pd.Series):
    """w_ij = sign_i * synapses_ij / in-subgraph-input_j.

    Returns W with W[j, i] = w_ij (row = postsynaptic, column = presynaptic),
    so that (W @ h)_j = sum_i w_ij h_i matches the recursion in the spec, and
    a diagnostic DataFrame with in-subgraph vs whole-connectome input per body.
    """
    order = bodies["bodyId"].to_numpy()
    idx = {b: i for i, b in enumerate(order)}
    K = len(order)

    insub_input = np.zeros(K, dtype=np.float64)
    for post, w in edges.groupby("body_post")["weight"].sum().items():
        insub_input[idx[post]] = w

    W = np.zeros((K, K), dtype=np.float64)
    for row in edges.itertuples(index=False):
        j = idx[row.body_post]
        i = idx[row.body_pre]
        denom = insub_input[j]
        if denom > 0:
            W[j, i] = signs.get(row.body_pre, 0.0) * row.weight / denom

    total_input_arr = total_input.reindex(order).fillna(0.0).to_numpy()
    coverage = np.divide(insub_input, total_input_arr,
                          out=np.zeros(K), where=total_input_arr > 0)

    diag = pd.DataFrame({
        "bodyId": order,
        "type": bodies["type"].to_numpy(),
        "somaSide": bodies["somaSide"].to_numpy(),
        "insub_input": insub_input,
        "total_input": total_input_arr,
        "coverage_frac": coverage,
    })

    print("\n--- input coverage: in-subgraph synapses / real total synapses ---")
    print(diag.groupby("type")["coverage_frac"].agg(["mean", "min", "max"])
          .to_string(float_format=lambda x: f"{x:.4f}"))

    return W, order, diag


def shuffle_edges(edges: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """SPEC section 5's control: same neurons, same in/out degree
    distribution, same signs, edges rewired at random.

    Implementation: permute the `body_post` column across all edge rows,
    leaving `body_pre` and `weight` attached to their original row. This
    exactly preserves, per neuron: out-degree and out-weight (a pre-neuron's
    rows, and the weights on them, are untouched) and in-degree, i.e. edge
    COUNT (the multiset of post ids is a permutation of itself, so every
    post id appears exactly as many times as before) -- only which specific
    pre now supplies which specific edge is randomised. Signs are a property
    of `body_pre` (Dale's law), so they travel with the row and are
    automatically preserved. In-WEIGHT per post-neuron is not preserved
    exactly (a post now receives whatever weight happened to be on the row
    reassigned to it) -- SPEC asks for degree distribution, not weight sum,
    and downstream row-normalisation renormalises per-post input anyway.

    A handful of reassignments land on self-loops (pre == post) or exact
    duplicates of an original edge; both are vanishingly rare at this
    density and are left in rather than hand-patched, to avoid quietly
    biasing the "random" in "rewired at random."
    """
    rng = np.random.default_rng(seed)
    shuffled = edges.copy()
    perm = rng.permutation(len(edges))
    shuffled["body_post"] = edges["body_post"].to_numpy()[perm]
    return shuffled


def build_shuffled(bodies: pd.DataFrame, edges: pd.DataFrame, total_input: pd.Series,
                    signs: pd.Series, seed: int = 0):
    """The section-5 control built from an already-extracted real subgraph
    (same bodies/edges/total_input/signs `load_cached.load` returns) --
    rewire the edges, then run them through the exact same normalisation
    pipeline as the real network."""
    shuffled_edges = shuffle_edges(edges, seed=seed)
    W_shuf, order_shuf, diag_shuf = build_weight_matrix(bodies, shuffled_edges, total_input, signs)
    return W_shuf, order_shuf, diag_shuf


def spectral_radius(W: np.ndarray, g: float) -> float:
    eig = np.linalg.eigvals(g * W)
    return float(np.max(np.abs(eig)))


def build_expanded(N: int = 60):
    """SPEC section 1b: sign-agnostic threshold expansion. Same pipeline as
    build(), but over the ~1200-neuron subgraph instead of the 315-neuron
    core -- extract_edges/build_signs/build_weight_matrix don't care how
    many bodies they're given."""
    import expand_subgraph

    print(f"Building expanded subgraph at N={N}...")
    bodies, per_pre = expand_subgraph.build(N)

    core = bodies[bodies["in_core"]]
    counts = core["type"].value_counts().to_dict()
    for t, expected in EXPECTED_COUNTS.items():
        got = counts.get(t, 0)
        assert got == expected, f"{t}: found {got}, expected {expected} (core unaffected by expansion)"

    print("\nExtracting body-level edges over the expanded subgraph "
          "(streams the full weights file once; cached after)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name=f"edges_circuit_expanded_N{N}.parquet"
    )
    assert_type_rollup(edges, bodies)
    report_dnp01_to_ttmn(edges, bodies)

    print("\nAssigning signs from consensus_nt...")
    signs = build_signs(bodies)

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W (g=1): {rho1:.4f}")

    print("\n--- E/I balance of the FINAL expanded subgraph (by neuron count) ---")
    sign_of_body = signs.reindex(bodies["bodyId"]).to_numpy()
    n_exc = int((sign_of_body > 0).sum())
    n_inh = int((sign_of_body < 0).sum())
    n_zero = int((sign_of_body == 0).sum())
    print(f"  excitatory: {n_exc}  inhibitory: {n_inh}  unsigned: {n_zero}  "
          f"(of {len(bodies)} total)")

    print("\n--- E/I balance by SYNAPSE WEIGHT flowing into the subgraph ---")
    e2 = edges.copy()
    e2["pre_sign"] = signs.reindex(e2["body_pre"]).to_numpy()
    w_exc = e2.loc[e2["pre_sign"] > 0, "weight"].sum()
    w_inh = e2.loc[e2["pre_sign"] < 0, "weight"].sum()
    w_zero = e2.loc[e2["pre_sign"] == 0, "weight"].sum()
    w_total = w_exc + w_inh + w_zero
    print(f"  excitatory: {w_exc:,} ({w_exc/w_total*100:.1f}%)  "
          f"inhibitory: {w_inh:,} ({w_inh/w_total*100:.1f}%)  "
          f"unsigned: {w_zero:,} ({w_zero/w_total*100:.1f}%)")

    print("\n--- input coverage for the ORIGINAL detector populations, before vs conceptually after ---")
    for t in ["LC4", "LPLC2", "DNp01"]:
        frac = diag.loc[diag["type"] == t, "coverage_frac"]
        print(f"  {t:8s} mean coverage now: {frac.mean()*100:.1f}%  "
              f"(min {frac.min()*100:.1f}%, max {frac.max()*100:.1f}%)")

    return bodies, edges, total_input, signs, W, order, diag


def build():
    print("Loading the 315 bodies of interest...")
    bodies = load_bodies()
    print(bodies["type"].value_counts().to_string())

    print("\nExtracting body-level edges (streams the full weights file once "
          "the first time; cached after)...")
    edges, total_input = extract_edges(bodies)
    assert_type_rollup(edges, bodies)
    report_dnp01_to_ttmn(edges, bodies)

    print("\nAssigning signs from consensus_nt...")
    signs = build_signs(bodies)

    print("\nBuilding the normalised weight matrix...")
    W, order, diag = build_weight_matrix(bodies, edges, total_input, signs)

    rho1 = spectral_radius(W, 1.0)
    print(f"\nSpectral radius of W (g=1): {rho1:.4f}")

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build()
