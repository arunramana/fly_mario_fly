"""
query_input_pools.py — pure investigation, no model changes.

Before touching phi or the normalisation: is there real inhibition in the
data that our 315-body subgraph is cutting away? Pull the FULL presynaptic
population of DNp01 and LPLC2 straight from the weights file (not restricted
to our subgraph) and look at neurotransmitter identity.

    python query_input_pools.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import mcns  # noqa: E402

SIGN = {"acetylcholine": "excitatory (ACh)", "dopamine": "excitatory (DA)",
        "gaba": "inhibitory (GABA)", "glutamate": "inhibitory (Glu)"}


def full_presynaptic_population(post_ids: np.ndarray, cache_name: str) -> pd.DataFrame:
    """Every (pre, post, weight) row in the WHOLE connectome landing on any
    of post_ids. post_ids can be small (unlike body_subgraph, pre is NOT
    restricted to any subset)."""
    cache_path = mcns.DERIVED / cache_name
    if cache_path.exists():
        print(f"  (cached) {cache_path.name}")
        return pd.read_parquet(cache_path)

    post_ids = np.asarray(sorted(set(int(b) for b in post_ids)), dtype=np.int64)
    K = len(post_ids)
    chunks = []
    total = 0
    import time
    start = time.time()
    for pre, post, w in mcns._edge_batches():
        iq = np.searchsorted(post_ids, post)
        np.clip(iq, 0, K - 1, out=iq)
        hit = post_ids[iq] == post
        if hit.any():
            chunks.append(pd.DataFrame({
                "body_pre": pre[hit], "body_post": post[hit], "weight": w[hit],
            }))
        total += len(pre)
        el = time.time() - start
        sys.stdout.write(f"\r  {total:,} edges scanned ({total/max(el,1e-6)/1e6:.1f} M/s)   ")
        sys.stdout.flush()
    sys.stdout.write("\n")

    out = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame(
        columns=["body_pre", "body_post", "weight"])
    out = out.groupby(["body_pre", "body_post"], as_index=False)["weight"].sum()
    out.to_parquet(cache_path, index=False)
    print(f"  cached -> {cache_path}")
    return out


def annotate(df: pd.DataFrame, ann: pd.DataFrame, nt: pd.DataFrame, id_col="body_pre") -> pd.DataFrame:
    ann_small = ann[["bodyId", "type", "superclass"]].rename(columns={"bodyId": id_col})
    nt_small = nt.rename(columns={"body": id_col})[[id_col, "consensus_nt"]]
    out = df.merge(ann_small, on=id_col, how="left").merge(nt_small, on=id_col, how="left")
    out["sign"] = out["consensus_nt"].str.lower().map(SIGN).fillna("unmapped/other")
    return out


def report_dnp01(ann, nt):
    print("\n" + "=" * 70)
    print("1+2. DNp01 -- FULL presynaptic population (whole connectome)")
    print("=" * 70)
    dnp01_ids = ann.loc[ann["type"] == "DNp01", "bodyId"].to_numpy()
    edges = full_presynaptic_population(dnp01_ids, "dnp01_full_presynaptic.parquet")
    edges = annotate(edges, ann, nt, id_col="body_pre")

    per_pre = (edges.groupby(["body_pre", "type", "sign"], dropna=False)["weight"]
               .sum().reset_index()
               .sort_values("weight", ascending=False))
    # a pre neuron might target only one of the two DNp01 bodies -- fold to one row per pre
    per_pre = per_pre.groupby(["body_pre", "type", "sign"], as_index=False)["weight"].sum()
    per_pre = per_pre.sort_values("weight", ascending=False)

    total = per_pre["weight"].sum()
    print(f"\nTotal synapses onto DNp01 (both bodies), whole connectome: {int(total):,}")
    print(f"(sanity check vs our subgraph's insub_input for DNp01)\n")

    print("Top 30 presynaptic partners of DNp01, by synapse count:")
    top30 = per_pre.head(30).copy()
    top30["frac_of_total"] = top30["weight"] / total
    print(top30.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\n--- excitatory / inhibitory split of DNp01's TOTAL input ---")
    split = per_pre.groupby("sign")["weight"].sum().sort_values(ascending=False)
    split_frac = split / total
    for s, w in split.items():
        print(f"  {s:20s} {int(w):>10,}  ({split_frac[s]*100:5.1f}%)")
    inhib_frac = split_frac.reindex(["inhibitory (GABA)", "inhibitory (Glu)"]).sum()
    print(f"\n  GABA + glutamate fraction of DNp01's total real input: {inhib_frac*100:.1f}%")

    return per_pre, edges


def report_lplc2(ann, nt):
    print("\n" + "=" * 70)
    print("3. LPLC2 -- FULL presynaptic population, looking for a shared pool")
    print("=" * 70)
    lplc2_ids = ann.loc[ann["type"] == "LPLC2", "bodyId"].to_numpy()
    n_lplc2 = len(lplc2_ids)
    edges = full_presynaptic_population(lplc2_ids, "lplc2_full_presynaptic.parquet")
    edges = annotate(edges, ann, nt, id_col="body_pre")

    total = edges["weight"].sum()
    print(f"\nTotal synapses onto LPLC2 (all 185), whole connectome: {int(total):,}")

    print("\n--- excitatory / inhibitory split of LPLC2's TOTAL input ---")
    split = edges.groupby("sign")["weight"].sum().sort_values(ascending=False)
    split_frac = split / total
    for s, w in split.items():
        print(f"  {s:20s} {int(w):>10,}  ({split_frac[s]*100:5.1f}%)")
    inhib_frac = split_frac.reindex(["inhibitory (GABA)", "inhibitory (Glu)"]).sum()
    print(f"\n  GABA + glutamate fraction of LPLC2's total real input: {inhib_frac*100:.1f}%")

    # breadth: for each presynaptic body, how many of the 185 LPLC2 neurons
    # does it reach? A shared inhibitory pool looks like: high breadth,
    # inhibitory sign, present across most/all of LPLC2.
    per_pre = edges.groupby(["body_pre", "type", "sign"], dropna=False).agg(
        total_weight=("weight", "sum"),
        n_lplc2_targets=("body_post", "nunique"),
    ).reset_index()
    per_pre["frac_of_lplc2_reached"] = per_pre["n_lplc2_targets"] / n_lplc2
    per_pre = per_pre.sort_values("n_lplc2_targets", ascending=False)

    print(f"\nTop 30 presynaptic partners of LPLC2, ranked by BREADTH "
          f"(how many of the {n_lplc2} LPLC2 neurons they reach):")
    print(per_pre.head(30).to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print("\nTop 30 presynaptic partners of LPLC2, ranked by total synapse weight:")
    by_weight = per_pre.sort_values("total_weight", ascending=False).head(30)
    print(by_weight.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # candidate shared pool: high-breadth AND inhibitory
    pool = per_pre[(per_pre["frac_of_lplc2_reached"] > 0.5) &
                   (per_pre["sign"].isin(["inhibitory (GABA)", "inhibitory (Glu)"]))]
    print(f"\nCandidates reaching >50% of LPLC2 neurons AND inhibitory: {len(pool)}")
    if len(pool):
        print(pool.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        types_in_pool = pool["type"].value_counts()
        print(f"\nTypes in this candidate pool:\n{types_in_pool.to_string()}")

    return per_pre, edges


if __name__ == "__main__":
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "superclass"])
    nt = mcns.load_neurotransmitters()

    dnp01_per_pre, dnp01_edges = report_dnp01(ann, nt)
    lplc2_per_pre, lplc2_edges = report_lplc2(ann, nt)
