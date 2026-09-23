"""
expand_subgraph.py — SPEC_jump.md section 1b: sign-agnostic threshold expansion.

The 313/315-neuron subgraph amputated 74-93% of real input to its own
neurons. This picks a threshold N (>= N total synapses onto ANY of
LC4/LPLC2/DNp01, whatever the neurotransmitter) that lands the expanded
subgraph in the 600-1500 neuron range, plus the five lateralised pooling
neurons regardless of N, plus the original core (LC4/LPLC2/DNp01/TTMn).

    python expand_subgraph.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import mcns  # noqa: E402
from fly.connectome.query_input_pools import full_presynaptic_population  # noqa: E402

CORE_TYPES = ["LC4", "LPLC2", "DNp01", "TTMn"]
POOLING_TYPES = ["PVLP011", "LPi21", "LPi2b", "Li39", "LPT59"]


def core_bodies(ann: pd.DataFrame) -> pd.DataFrame:
    return ann[ann["type"].isin(CORE_TYPES)].copy()


def combined_presynaptic_weight(ann: pd.DataFrame) -> pd.DataFrame:
    """Per presynaptic body: total synapses onto ANY of LC4/LPLC2/DNp01
    (not TTMn -- TTMn is the effector, not a detector/GF input target)."""
    dnp01_ids = ann.loc[ann["type"] == "DNp01", "bodyId"].to_numpy()
    lplc2_ids = ann.loc[ann["type"] == "LPLC2", "bodyId"].to_numpy()
    lc4_ids = ann.loc[ann["type"] == "LC4", "bodyId"].to_numpy()

    e_dnp01 = full_presynaptic_population(dnp01_ids, "dnp01_full_presynaptic.parquet")
    e_lplc2 = full_presynaptic_population(lplc2_ids, "lplc2_full_presynaptic.parquet")
    e_lc4 = full_presynaptic_population(lc4_ids, "lc4_full_presynaptic.parquet")

    allE = pd.concat([e_dnp01, e_lplc2, e_lc4], ignore_index=True)
    per_pre = allE.groupby("body_pre", as_index=False)["weight"].sum()
    per_pre = per_pre.rename(columns={"weight": "total_weight_onto_core"})
    return per_pre.sort_values("total_weight_onto_core", ascending=False)


def choose_N(per_pre: pd.DataFrame, ann: pd.DataFrame, target_lo=600, target_hi=1500):
    core = set(core_bodies(ann)["bodyId"])
    candidates = per_pre[~per_pre["body_pre"].isin(core)]

    print("count of NEW (non-core) neurons at various N thresholds:")
    for N in [1, 2, 5, 10, 20, 30, 40, 50, 60, 70, 80, 100, 120, 150, 200, 300]:
        n = int((candidates["total_weight_onto_core"] >= N).sum())
        flag = "  <-- in range" if target_lo <= n <= target_hi else ""
        print(f"  N={N:4d}: {n:5d} neurons{flag}")

    return candidates


def build(N: int):
    ann = mcns.load_annotations(["bodyId", "type", "somaSide"])
    core = core_bodies(ann)
    per_pre = combined_presynaptic_weight(ann)
    candidates = choose_N(per_pre, ann)

    core_ids = set(core["bodyId"])
    threshold_ids = set(candidates.loc[candidates["total_weight_onto_core"] >= N, "body_pre"])
    pool_ids = set(ann.loc[ann["type"].isin(POOLING_TYPES), "bodyId"])

    all_ids = core_ids | threshold_ids | pool_ids
    print(f"\nN = {N}")
    print(f"  core (LC4/LPLC2/DNp01/TTMn):        {len(core_ids)}")
    print(f"  threshold-expansion (new neurons):  {len(threshold_ids - core_ids)}")
    print(f"  pooling exception, not already in:  {len(pool_ids - core_ids - threshold_ids)}")
    print(f"  TOTAL:                              {len(all_ids)}")

    bodies = ann[ann["bodyId"].isin(all_ids)].copy()
    bodies["in_core"] = bodies["bodyId"].isin(core_ids)
    bodies["in_pool_exception"] = bodies["bodyId"].isin(pool_ids - core_ids - threshold_ids)
    return bodies, per_pre


if __name__ == "__main__":
    ann = mcns.load_annotations(["bodyId", "type"])
    per_pre = combined_presynaptic_weight(ann)
    choose_N(per_pre, ann)
