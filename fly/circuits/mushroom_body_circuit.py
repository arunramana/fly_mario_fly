"""
mushroom_body_circuit.py -- KC + MBON + PAM/PPL/PPM dopaminergic core.
See SPEC_mushroom_body.md. Core = the three real populations themselves
(no presynaptic-threshold expansion -- unlike every other circuit here,
this one's whole point is the connectivity AMONG these three groups, not
what drives them from outside). Same build_signs/build_weight_matrix
pipeline as everywhere else in this project.

Real counts, asserted at load time (SPEC section 0 -- these do NOT match
the "4,554 KC -> 104 MBON" figure repeated in docs/RUNS.md's earlier
"Still open" notes; that figure was never checked against this connectome
file, this one is):
    KC   (class == 'Kenyon_Cell'): 4064
    MBON (class == 'MBON'):          97
    DAN  (type matches ^PAM|^PPL|^PPM): 354, 32 distinct types

    python mushroom_body_circuit.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
import mcns  # noqa: E402

from fly.connectome import circuit

EXPECTED_KC = 4064
EXPECTED_MBON = 97
EXPECTED_DAN = 354
DAN_TYPE_RE = re.compile(r"^(PAM|PPL|PPM)")


def core_bodies(ann: pd.DataFrame) -> pd.DataFrame:
    kc = ann[ann["class"] == "Kenyon_Cell"].copy()
    kc["role"] = "KC"
    mbon = ann[ann["class"] == "MBON"].copy()
    mbon["role"] = "MBON"
    is_dan = ann["type"].astype(str).str.match(DAN_TYPE_RE)
    dan = ann[is_dan].copy()
    dan["role"] = "DAN"
    # PAM (reward, literature-canonical) vs everything else prefixed
    # PPL/PPM (lumped as punishment -- PPM's role is mixed in the
    # literature, a stated judgement call per SPEC section 3, not a
    # verified split).
    dan["dan_channel"] = np.where(dan["type"].astype(str).str.startswith("PAM"),
                                   "reward", "punish")

    for name, df, expected in (("KC", kc, EXPECTED_KC), ("MBON", mbon, EXPECTED_MBON),
                                ("DAN", dan, EXPECTED_DAN)):
        got = len(df)
        assert got == expected, (
            f"{name}: found {got} bodies, expected {expected}. "
            "The connectome data changed underneath us -- stop and check."
        )

    core = pd.concat([kc, mbon, dan], ignore_index=True)
    return core


def build_full():
    ann = mcns.load_annotations(["bodyId", "type", "somaSide", "somaNeuromere", "class"])
    bodies = core_bodies(ann)
    bodies = bodies.sort_values(["role", "type", "somaSide", "bodyId"]).reset_index(drop=True)

    print(f"Mushroom body core: KC={int((bodies.role=='KC').sum())} "
          f"MBON={int((bodies.role=='MBON').sum())} DAN={int((bodies.role=='DAN').sum())} "
          f"(reward/PAM={int((bodies.dan_channel=='reward').sum())}, "
          f"punish/PPL+PPM={int((bodies.dan_channel=='punish').sum())})")

    print("\nExtracting body-level edges over the KC/MBON/DAN subgraph "
          "(streams the full weights file once; cached after -- this is a "
          "~4500-body extraction, expect the first pass to take a few "
          "minutes)...")
    edges, total_input = mcns.body_subgraph(
        bodies["bodyId"], cache_name="edges_mushroom_body.parquet"
    )

    print("\nAssigning signs from consensus_nt (circuit.build_signs's own "
          "'sign by type' printout below only lists the JUMP circuit's four "
          "types, not ours -- harmless, real per-role counts follow)...")
    signs = circuit.build_signs(bodies)
    sign_of_body = signs.reindex(bodies["bodyId"]).to_numpy()
    for role in ("KC", "MBON", "DAN"):
        sub = sign_of_body[bodies["role"].to_numpy() == role]
        print(f"    {role:5s} +1: {int((sub > 0).sum()):4d}  "
              f"-1: {int((sub < 0).sum()):4d}  0: {int((sub == 0).sum()):4d}")

    print("\nBuilding the normalised weight matrix (row-normalised by each "
          "post-neuron's real in-subgraph input, same convention as every "
          "other circuit here)...")
    W, order, diag = circuit.build_weight_matrix(bodies, edges, total_input, signs)

    role_of = bodies.set_index("bodyId")["role"]
    e2 = edges.copy()
    e2["pre_role"] = e2.body_pre.map(role_of)
    e2["post_role"] = e2.body_post.map(role_of)
    print("\n--- real edge counts among KC/MBON/DAN (sanity check vs SPEC section 0) ---")
    summary = e2.groupby(["pre_role", "post_role"]).agg(
        synapses=("weight", "sum"), pairs=("weight", "size"),
        pre_n=("body_pre", "nunique"), post_n=("body_post", "nunique"))
    print(summary.to_string())

    return bodies, edges, total_input, signs, W, order, diag


if __name__ == "__main__":
    build_full()
