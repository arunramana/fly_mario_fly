"""Part L2c sections 1-2 (graph facts): MDN in MaleCNS, its inputs / outputs, and the routes into it. Same tools as l2b_smell (o0_sim: N5 graph, k=3 rule).
python -m flyrun.l2c_graph -> prints, writes runs/L2c_graph.json, runs/L2c_mdn_inputs.csv"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import o0_sim as S

OUT = Path(__file__).resolve().parent / "runs"
ID, TYPES, SIDE, SIGNS = S.IDS, S.TYPES, S.SIDE, S.SIGNS
n = len(ID)
Wc = sp.csr_matrix((S.WSYN, (S.POST, S.PRE)), shape=(n, n))
Wn = sp.csr_matrix((SIGNS[S.PRE] * S.WSYN / np.maximum(S.TOTAL_IN[S.POST], 1.0), (S.POST, S.PRE)), shape=(n, n))
MDN = TYPES == "MDN"
DNP09 = TYPES == "DNp09"
DNA = np.isin(TYPES, ["DNa01", "DNa02"])
res = {}
st_ids = set(S.ST.bodyId.astype(int))
cur = pd.read_parquet(S.CACHE / "steer_jo_orn_bodies.parquet")
cur_ids = set(cur.bodyId.astype(int)) | st_ids         # the 881 production brain

# ---- 1. MDN
print("MDN bodies:", [(int(ID[i]), SIDE[i], "sign %+d" % SIGNS[i], "in model" if int(ID[i]) in cur_ids else "NOT in model") for i in np.flatnonzero(MDN)])
res["mdn"] = [dict(body=int(ID[i]), side=SIDE[i], sign=int(SIGNS[i]), in_model=int(ID[i]) in cur_ids, total_in=float(S.TOTAL_IN[i])) for i in np.flatnonzero(MDN)]
m = MDN[S.POST]
d = pd.DataFrame(dict(pre_type=TYPES[S.PRE[m]], pre_side=SIDE[S.PRE[m]], post_side=SIDE[S.POST[m]], w=S.WSYN[m], sign=SIGNS[S.PRE[m]]))
inp = d.groupby("pre_type").agg(syn=("w", "sum"), n_neurons=("w", "size"), sign=("sign", "mean")).sort_values("syn", ascending=False)
inp["share_of_total_in"] = inp.syn / S.TOTAL_IN[MDN].sum()
print("MDN input: %d synapses in >=5 edges of %d total input" % (d.w.sum(), S.TOTAL_IN[MDN].sum()))
print(inp.head(15).to_string())
inp.head(40).to_csv(OUT / "L2c_mdn_inputs.csv", lineterminator="\n")
res["mdn_inputs_top15"] = inp.head(15).reset_index().to_dict("records")
sides = d.groupby(["post_side", "pre_side"]).w.sum().unstack(fill_value=0)
print("input synapses by MDN side (rows) x presyn side (cols):\n", sides)
res["mdn_input_sides"] = sides.to_dict()
# outputs
o = (S.PRE[:, None] if False else None)
mo = MDN[S.PRE]
od = pd.DataFrame(dict(post_type=TYPES[S.POST[mo]], w=S.WSYN[mo])).groupby("post_type").w.agg(["sum", "size"]).sort_values("sum", ascending=False)
print("MDN output top 12 (type: synapses, neurons):\n", od.head(12).to_string())
res["mdn_outputs_top12"] = od.head(12).reset_index().to_dict("records")


def hops(src, k=6):
    dist = np.full(n, 99); dist[src] = 0
    fr = np.zeros(n); fr[src] = 1
    seen = np.zeros(n, bool); seen[src] = True
    for h in range(1, k + 1):
        nx = ((Wc @ fr) > 0) & ~seen
        dist[nx] = h; seen |= nx; fr = nx.astype(float)
    return dist


def mass(src, tgt, hmax=3):
    v = np.zeros(n); v[src] = 1.0
    out = {}
    for h in range(1, hmax + 1):
        v = Wn @ v
        out[h] = float(v[tgt].sum())
    return out


src = np.flatnonzero(MDN)
dm = hops(src)
rows = []
for name, tg in (("DNp09", DNP09), ("DNa01/02", DNA)):
    for ds in "LR":
        t = np.flatnonzero(tg & (SIDE == ds))
        mm = mass(src, t, 3)
        rows.append(dict(target=name, side=ds, direct_syn=int(Wc[t][:, src].sum()), min_hops=int(dm[t].min()), mass_h1=mm[1], mass_h2=mm[2], mass_h3=mm[3]))
        # per MDN side
        for ms in "LR":
            s1 = np.flatnonzero(MDN & (SIDE == ms))
            rows[-1][f"mass_h2_from_MDN_{ms}"] = mass(s1, t, 2)[2]
mt = pd.DataFrame(rows)
pd.set_option("display.width", 250, "display.max_columns", 30)
print("MDN -> walking / steering (signed mass = g-free linear gain per hop):\n", mt.to_string(index=False))
res["mdn_to_targets"] = rows

# ---- 2. routes into MDN
orn_all = sorted(t for t in set(TYPES) if t.startswith("ORN_"))
print("ORN types:", len(orn_all))
ORN_SETS = {"V": ["ORN_V"], "DA2": ["ORN_DA2"], "DL5": ["ORN_DL5"], "DC4": ["ORN_DC4"], "VM... none": []}
SETS = {"smell V (CO2)": ["ORN_V"], "smell DA2 (geosmin)": ["ORN_DA2"], "smell DL5": ["ORN_DL5"], "smell DC4 (acid, Ir64a)": ["ORN_DC4"],
        "vision LC16": ["LC16"], "vision LPLC2": ["LPLC2"], "vision LC4": ["LC4"], "MBON (all 97)": [t for t in set(TYPES) if t.startswith("MBON")]}
rows, adds = [], {}
for name, tl in SETS.items():
    for ant in ("LR" if not name.startswith("MBON") else ["LR"]):
        pass
    msk0 = np.isin(TYPES, tl)
    if not msk0.any():
        print(name, "no neurons"); continue
    for side in ("L", "R", "all"):
        s = np.flatnonzero(msk0 & ((SIDE == side) if side != "all" else True))
        if not len(s):
            continue
        dd = hops(s)
        r = dict(route=name, side=side, n=len(s), in_model=int(np.isin(ID[s], list(cur_ids)).sum()), direct_syn_MDN=int(Wc[src][:, s].sum()), min_hops_MDN=int(dd[src].min()))
        mm = mass(s, src, 3)
        r.update(mass_h1=mm[1], mass_h2=mm[2], mass_h3=mm[3])
        for ms in "LR":
            r[f"mass_h3_MDN_{ms}"] = mass(s, np.flatnonzero(MDN & (SIDE == ms)), 3)[3]
        rows.append(r)
    kn = [int(b) for b in S.kn_new_ids(msk0, MDN)]
    new = [b for b in kn if b not in cur_ids]
    orn_new = [b for b in new if TYPES[np.searchsorted(ID, b)] in tl]
    inter = [b for b in new if b not in set(orn_new) and not MDN[np.searchsorted(ID, b)]]
    adds[name] = new
    bt = pd.Series(TYPES[np.searchsorted(ID, inter)]).value_counts().head(8).to_dict() if inter else {}
    print(f"{name}: k/N set {len(kn)}; new to the 881 brain {len(new)} = {len(orn_new)} sources + {len(inter)} intermediates + {int(sum(MDN[np.searchsorted(ID, b)] for b in new))} MDN; intermediates: {bt}")
    res.setdefault("kN", {})[name] = dict(total=len(kn), new=len(new), sources=len(orn_new), intermediates=len(inter), by_type=bt)
rt = pd.DataFrame(rows)
print(rt.to_string(index=False))
rt.to_csv(OUT / "L2c_routes.csv", index=False, lineterminator="\n")
res["routes"] = rows
json.dump({k: v for k, v in res.items()}, open(OUT / "L2c_graph.json", "w"), indent=1, default=float)
json.dump({k: v for k, v in adds.items()}, open(OUT / "L2c_adds.json", "w"))
