# What this file does, in plain English:
# Builds the small network that drives the Down and Up buttons: five types of
# descending neurons that listen to the looming-detector neurons (LC4, LPLC2,
# LPLC1), plus every detector neuron that gives them at least 60 synapses. It
# is built from the real synapse counts the same way as the walk-backwards
# network. The data is extracted once (cached in ../data/derived) and reloaded
# quickly after. docs/SPEC_learning_v3.md section A7 explains the choice of
# neurons and why the button roles are a hypothesis.
"""posture_circuit.py -- DNp03/DNp06/DNp11 (Down muscle) and DNg40/DNp05 (Up
muscle) plus their LC4/LPLC2/LPLC1 input neurons (>= N_THRESHOLD synapses onto
the core). Same pipeline as mdn_circuit.py (circuit.build_signs /
build_weight_matrix); one streaming pass the first time, cached after.

    python -m fly.circuits.posture_circuit
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import mcns  # noqa: E402

from fly.connectome import circuit

DOWN_TYPES = ("DNp03", "DNp06", "DNp11")
UP_TYPES = ("DNg40", "DNp05")
CORE_TYPES = DOWN_TYPES + UP_TYPES
INPUT_TYPES = ("LC4", "LPLC2", "LPLC1")
N_THRESHOLD = 60
# The one streaming pass covers every descending neuron plus the looming LC types;
# the edge cache is shared by any circuit built from that pool.
POOL_TYPES = ("LC4", "LPLC2", "LPLC1", "LC6", "LC16", "LC11", "LC17", "LC9", "LC10a")
CACHE_NAME = "edges_dn_vis_learning_v3.parquet"


def build_full(N: int = N_THRESHOLD):
    ann = mcns.load_annotations(["bodyId", "type", "superclass", "somaSide", "somaNeuromere"])
    dn = ann[ann["superclass"].astype(str).str.contains("descending", case=False)]
    pool = pd.concat([dn, ann[ann["type"].isin(POOL_TYPES)]])
    edges, total_input = mcns.body_subgraph(pool["bodyId"], cache_name=CACHE_NAME)

    core = ann[ann["type"].isin(CORE_TYPES)]
    for t in CORE_TYPES:
        assert (core["type"] == t).sum() > 0, f"{t}: no neurons found -- the connectome data changed"
    core_ids = set(core["bodyId"])
    inputs = ann[ann["type"].isin(INPUT_TYPES)]
    onto_core = edges[edges["body_post"].isin(core_ids) & edges["body_pre"].isin(set(inputs["bodyId"]))]
    per_pre = onto_core.groupby("body_pre")["weight"].sum()
    keep_inputs = set(per_pre[per_pre >= N].index)

    bodies = ann[ann["bodyId"].isin(core_ids | keep_inputs)].copy()
    bodies = bodies.sort_values(["type", "somaSide", "bodyId"]).reset_index(drop=True)
    bodies["in_core"] = bodies["bodyId"].isin(core_ids)
    ids = set(bodies["bodyId"])
    edges = edges[edges["body_pre"].isin(ids) & edges["body_post"].isin(ids)].reset_index(drop=True)
    print(f"posture circuit N={N}: core {len(core_ids)} ({core['type'].value_counts().to_dict()}), "
          f"inputs {len(keep_inputs)} ({inputs[inputs['bodyId'].isin(keep_inputs)]['type'].value_counts().to_dict()})")

    signs = circuit.build_signs(bodies)
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)
    print(f"Spectral radius of W_posture (g=1): {circuit.spectral_radius(W, 1.0):.4f}")
    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
