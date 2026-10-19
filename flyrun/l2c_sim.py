"""Part L2c section 3 (scratch builds, default brain untouched): add the k/N set (and a smaller 'top intermediates' set) for each route into MDN, drive the input 1-60 with HOME_R on,
read MDN, DNp09 and DNa L-R, and compare MDN with GF at the looming trigger and DNp09 at normal walking. Uses l2c_graph's adds (runs/L2c_adds.json).
python -m flyrun.l2c_sim -> runs/L2c_drive.csv, runs/L2c_ref.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import o0_sim as S

OUT = Path(__file__).resolve().parent / "runs"
ID, TYPES, SIDE, SIGNS = S.IDS, S.TYPES, S.SIDE, S.SIGNS
n = len(ID)
Wn = sp.csr_matrix((SIGNS[S.PRE] * S.WSYN / np.maximum(S.TOTAL_IN[S.POST], 1.0), (S.POST, S.PRE)), shape=(n, n))
MDNm = TYPES == "MDN"
st_ids = set(S.ST.bodyId.astype(int))
cur = pd.read_parquet(S.CACHE / "steer_jo_orn_bodies.parquet")
extra_cur = [int(b) for b in cur.bodyId if int(b) not in st_ids]
adds = json.load(open(OUT / "L2c_adds.json"))
SRC = {"smell V (CO2)": ["ORN_V"], "smell DA2 (geosmin)": ["ORN_DA2"], "smell DL5": ["ORN_DL5"], "smell DC4 (acid, Ir64a)": ["ORN_DC4"], "vision LC16": ["LC16"],
       "vision LPLC2": ["LPLC2"], "vision LC4": ["LC4"], "MBON (all 97)": [t for t in set(TYPES) if t.startswith("MBON")]}
TOPN = 20                 # INVENTED: how many top intermediates the 'small' build keeps (80 % of the 2-hop mass is the aim, reported)


class Net2(S.Net):
    def __init__(self, W, b):
        super().__init__(W, b)
        t = b.type.to_numpy()
        self.m["MDN"] = t == "MDN"

    def final(self, I, frames=100):
        h = np.zeros(self.K)
        peak = {k: 0.0 for k in ("MDN", "DNp09", "GF", "TTMn")}
        for _ in range(frames):
            for _ in range(S.SUBSTEPS):
                h = (1 - S.ALPHA) * h + S.ALPHA * np.clip(S.G * (self.W @ h) + I, 0.0, S.CLIP)
            for k in peak:
                peak[k] = max(peak[k], float(h[self.m[k]].mean()))
        r = {k: float(h[self.m[k]].mean()) for k in ("MDN", "DNp09", "DNa_L", "DNa_R", "GF", "TTMn")}
        r["steer"] = r["DNa_R"] - r["DNa_L"]
        r.update({f"peak_{k}": v for k, v in peak.items()})
        r["MDN_L"] = float(h[self.m["MDN"] & (self.b.side.to_numpy() == "L")].mean())
        r["MDN_R"] = float(h[self.m["MDN"] & (self.b.side.to_numpy() == "R")].mean())
        return r


def small_set(name):
    """sources + the TOPN intermediates carrying most 2-hop signed-|mass| onto MDN (+ MDN)."""
    tl = SRC[name]
    new = adds[name]
    ix = np.searchsorted(ID, new)
    x = np.isin(TYPES, tl).astype(float)
    fwd = [x]                                       # signed mass out of the sources after a hops
    for _ in range(3):
        fwd.append(Wn @ fwd[-1])
    e = MDNm.astype(float)
    bwd = [e]                                       # signed weight of each neuron onto MDN over b hops
    for _ in range(3):
        bwd.append(Wn.T @ bwd[-1])
    c = np.zeros(n)
    for a in (1, 2):
        for b in (1, 2):
            if a + b in (2, 3):                     # paths of 2-3 hops, the k = 3 horizon
                c += np.abs(fwd[a] * bwd[b])
    inter = [b for b, i in zip(new, ix) if TYPES[i] not in tl and not MDNm[i]]
    ii = np.searchsorted(ID, inter)
    order = np.argsort(-c[ii])
    keep = [inter[j] for j in order[:TOPN] if c[ii[j]] > 0]
    share = float(c[ii][order[:TOPN]].sum() / max(c[ii].sum(), 1e-30))
    return [b for b, i in zip(new, ix) if TYPES[i] in tl or MDNm[i]] + keep, share


# ---- references
th_dth = S.onset_inputs()
th, dth = th_dth[0], th_dth[1]
base = Net2(*S.build(extra_cur))                                    # the production 881 brain (no MDN)
ref0 = Net2(*S.build(extra_cur + [int(b) for b in ID[MDNm]]))       # + MDN only, nothing driving it
refs = {}
I = ref0.vec(LC10a_R=S.HOME_R)
refs["walk: HOME_R only"] = ref0.final(I)
I = ref0.vec(LPLC2_R=th, LC4_R=dth, LC10a_R=S.HOME_R)
refs["looming trigger (theta %.2f rad, dtheta %.4f) + HOME_R" % (th, dth)] = ref0.final(I)
print(pd.DataFrame(refs).T[["GF", "peak_GF", "TTMn", "peak_TTMn", "DNp09", "MDN", "steer"]].to_string())
json.dump(dict(refs=refs, theta=th, dtheta=dth), open(OUT / "L2c_ref.json", "w"), indent=1)

LEV = (0, 1, 2, 5, 10, 20, 30, 40, 60)
rows = []


def run_build(label, route, ids, kind):
    net = Net2(*S.build(extra_cur + list(ids)))
    bid = net.b.bodyId.to_numpy()
    tl = SRC[route]
    for side in ("R", "L", "LR"):
        sel = np.isin(TYPES, tl) & (np.isin(SIDE, list(side)) if True else True)
        idx = np.flatnonzero(np.isin(bid, ID[sel]))
        if not len(idx):
            continue
        for lvl in LEV:
            I = net.vec(LC10a_R=S.HOME_R)
            I[idx] = lvl
            r = net.final(I)
            rows.append(dict(route=route, build=label, kind=kind, K=net.K, side=side, n_driven=len(idx), level=lvl, **r))
    return net


for route in SRC:
    if route not in adds:
        continue
    ids_small, share = small_set(route)
    print(route, "small set", len(ids_small), "share of 2-hop |mass| kept", round(share, 3), "| k/N set", len(adds[route]), flush=True)
    run_build("small", route, ids_small, "small(top%d)" % TOPN)
    if len(adds[route]) <= 2500:
        run_build("kN", route, adds[route], "k/N")
    # LC16 driven the way looming drives LPLC2: theta of a Koopa (h 24 px) at distance d
    if route == "vision LC16":
        for label, ids in (("small", ids_small), ("kN", adds[route])):
            net = Net2(*S.build(extra_cur + list(ids)))
            bid = net.b.bodyId.to_numpy()
            for side in ("R", "LR"):
                idx = np.flatnonzero(np.isin(bid, ID[(TYPES == "LC16") & np.isin(SIDE, list(side))]))
                for d in (20, 30, 40, 50, 60):
                    thk = 2 * np.arctan(24 / (2 * d))
                    I = net.vec(LC10a_R=S.HOME_R)
                    I[idx] = thk
                    rows.append(dict(route="vision LC16 (theta of a Koopa)", build=label, kind="theta", K=net.K, side=side, n_driven=len(idx), level=d, theta=thk, **net.final(I)))
    if route in ("vision LPLC2", "vision LC4"):
        for label, ids in (("small", ids_small), ("kN", adds[route])):
            net = Net2(*S.build(extra_cur + list(ids)))
            rows.append(dict(route=route + " (at the looming trigger)", build=label, kind="trigger", K=net.K, side="R", n_driven=0, level=-1, **net.final(net.vec(LPLC2_R=th, LC4_R=dth, LC10a_R=S.HOME_R))))
            rows.append(dict(route=route + " (HOME_R only)", build=label, kind="trigger", K=net.K, side="R", n_driven=0, level=0, **net.final(net.vec(LC10a_R=S.HOME_R))))
    pd.DataFrame(rows).to_csv(OUT / "L2c_drive.csv", index=False, lineterminator="\n")
df = pd.DataFrame(rows)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(df[df.level.isin([0, 5, 20, 60]) | (df.kind == "theta")][["route", "build", "K", "side", "level", "MDN", "DNp09", "steer", "GF", "TTMn"]].to_string(index=False))
