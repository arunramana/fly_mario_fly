"""Part M2 brain: the Q-brain (W_steer + 20 JO neurons, 656) + ONLY the attractive-ORN -> DNa path neurons of O0, pruned to the smallest set that keeps the O0 ipsilateral result.
Starting set = the k = 3 / N = 5 set from the attractive ORNs (DM1, VA2, DM4; both antennae) to DNa01/02 (O0: 235 new neurons). The intermediates (not the 179 ORNs themselves)
are then removed greedily, least influential first, as long as the HOME_R-on steering numbers stay within tolerance of the full set. Saves tutorials/_cache/W_steer_jo_orn.npy +
steer_jo_orn_bodies.parquet and the 5 shuffles of the SAME count matrix (Part 6b rule): W_steer_jo_orn_shuf{0..4}_rn.npy.
python -m flyrun.m2_brain"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import o0_sim as S
from .brain import CACHE
from .q1_brain import jo20
from .shuffle import build_W, degree_shuffle

ROOT = Path(__file__).resolve().parent
ATTR = ["ORN_DM1", "ORN_VA2", "ORN_DM4"]
LEVELS = (0, 20, 50)


def metrics(extra_ids, levels=LEVELS):
    """HOME_R on; a constant level into the left (right) antenna's attractive ORNs; steer = mean DNa_R - mean DNa_L after 100 frames."""
    net = S.Net(*S.build(list(extra_ids)))
    ids = net.b.bodyId.to_numpy()
    out = {}
    for ant in "LR":
        idx = np.flatnonzero(np.isin(ids, S.IDS[np.isin(S.TYPES, ATTR) & (S.SIDE == ant)]))
        for lvl in levels:
            I = net.vec(LC10a_R=S.HOME_R)
            I[idx] = lvl
            tr = net.run(lambda f: I, 100)
            out[f"{ant}{lvl}"] = float(tr["DNa_R"][-1] - tr["DNa_L"][-1])
    return net, out


def main():
    jo = list(jo20())
    orn_mask = np.isin(S.TYPES, ATTR)
    full = [int(b) for b in S.kn_new_ids(orn_mask, np.isin(S.TYPES, ["DNa01", "DNa02"]))]
    st = set(S.ST.bodyId.astype(int))
    full = [b for b in full if b not in st]
    orn_ids = set(int(b) for b in S.IDS[orn_mask])
    inter = [b for b in full if b not in orn_ids]
    print("k/N set: new", len(full), "= ORNs", len(full) - len(inter), "+ intermediates", len(inter))
    _, ref = metrics(jo + full)
    print("full set:", {k: round(v, 5) for k, v in ref.items()})
    # importance of each intermediate: how much the steering numbers move when it is removed alone
    imp = {}
    for b in inter:
        _, m = metrics(jo + [x for x in full if x != b])
        imp[b] = sum(abs(m[k] - ref[k]) for k in ("L50", "R50", "L20"))
    order = sorted(inter, key=lambda b: imp[b])
    keep = list(full)
    removed = []
    ok = lambda m: abs(m["L50"] - ref["L50"]) <= 0.1 * abs(ref["L50"]) and abs(m["L20"] - ref["L20"]) <= 0.1 * abs(ref["L20"]) + 0.001 and m["R50"] > 0.04 and m["L50"] < -0.01
    for b in order:
        trial = [x for x in keep if x != b]
        _, m = metrics(jo + trial)
        if ok(m):
            keep, removed = trial, removed + [b]
    net, fin = metrics(jo + keep)
    print("pruned set:", len(keep), "(", len(keep) - len([b for b in keep if b in orn_ids]), "intermediates +", len([b for b in keep if b in orn_ids]), "ORNs); removed", len(removed))
    print("pruned:", {k: round(v, 5) for k, v in fin.items()})
    types = pd.Series(S.TYPES[np.isin(S.IDS, [b for b in keep if b not in orn_ids])]).value_counts().to_dict()
    print("intermediates kept by type:", types)
    W, bodies, counts, sign = S.build(jo + keep, return_counts=True)
    np.save(CACHE / "W_steer_jo_orn.npy", W)
    out = pd.DataFrame(dict(bodyId=bodies.bodyId, type=bodies.type, somaSide=bodies.side, sign=sign))
    st_b = pd.read_parquet(CACHE / "steer_bodies.parquet")
    out["nt"] = list(st_b.nt) + [""] * (len(out) - len(st_b))
    out.to_parquet(CACHE / "steer_jo_orn_bodies.parquet", index=False)
    for seed in range(5):
        cs, done = degree_shuffle(counts, seed=seed)
        np.save(CACHE / f"W_steer_jo_orn_shuf{seed}_rn.npy", build_W(cs, sign))
    json.dump(dict(full_new=len(full), full_orns=len(full) - len(inter), full_intermediates=len(inter), kept_intermediates=len(keep) - len(full) + len(inter) if False else len([b for b in keep if b not in orn_ids]),
                   kept_total=len(keep), n_neurons=len(bodies), ref_full=ref, final=fin, kept_types=types,
                   removed_n=len(removed)), open(ROOT / "runs" / "M2_brain.json", "w"), indent=1, default=float)
    print("brain", W.shape)


if __name__ == "__main__":
    main()
