"""The escape+walk+steer network (nb 04/09/20): W_steer.npy + its body table."""
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "tutorials" / "_cache"

# (name, cell types, side or None for both). Every one must be present in W_steer.
REQUIRED = [
    ("LC4_L", ["LC4"], "L"), ("LC4_R", ["LC4"], "R"),
    ("LPLC2_L", ["LPLC2"], "L"), ("LPLC2_R", ["LPLC2"], "R"),
    ("DNp01", ["DNp01"], None),
    ("TTMn", ["TTMn"], None),
    ("DNp09", ["DNp09"], None),
    ("LC10a_L", ["LC10a"], "L"), ("LC10a_R", ["LC10a"], "R"),
    ("DNa_L", ["DNa01", "DNa02"], "L"), ("DNa_R", ["DNa01", "DNa02"], "R"),
]


@dataclass
class Brain:
    W: np.ndarray
    bodies: pd.DataFrame
    masks: dict  # name -> boolean array over neurons

    @property
    def K(self):
        return self.W.shape[0]

    def counts(self):
        return {k: int(m.sum()) for k, m in self.masks.items()}


def load_brain(cache=CACHE):
    # FLYRUN_WFILE lets a worker pool load a control matrix (Part 5: W_steer_shuf0.npy); default = the real one
    W = np.load(Path(cache) / os.environ.get("FLYRUN_WFILE", "W_steer.npy"))
    # FLYRUN_BODIES: the matching body table for a control / extended matrix (Part Q1: steer_jo_bodies.parquet); default = the real one
    bodies = pd.read_parquet(Path(cache) / os.environ.get("FLYRUN_BODIES", "steer_bodies.parquet"))
    bodies["somaSide"] = bodies["somaSide"].fillna("")
    types = bodies["type"].to_numpy()
    sides = bodies["somaSide"].to_numpy()
    masks = {}
    for name, tlist, side in REQUIRED:
        m = np.isin(types, tlist)
        if side is not None:
            m &= sides == side
        masks[name] = m
    jo = np.char.startswith(types.astype(str), "JO")
    if jo.any():                      # Part Q1: Johnston's organ neurons, present only in the extended brain (W_steer_jo.npy)
        masks["JO"] = jo
    orn = np.char.startswith(types.astype(str), "ORN")
    if orn.any():                     # Part M2: attractive olfactory receptor neurons, present only in the ORN brain (W_steer_jo_orn.npy)
        masks["ORN_L"], masks["ORN_R"] = orn & (sides == "L"), orn & (sides == "R")
    return Brain(W=W, bodies=bodies, masks=masks)


def step(h, W, g, I_t, alpha, clip):
    """One leaky rate update (nb 04/09)."""
    drive = g * (W @ h) + I_t
    return (1.0 - alpha) * h + alpha * np.clip(drive, 0.0, clip)


if __name__ == "__main__":
    b = load_brain()
    print("W", b.W.shape, "bodies", len(b.bodies))
    for k, v in b.counts().items():
        print(f"  {k:8s} {v}")
