"""Part O0, sections 1-2 (graph facts only): Johnston's organ -> GF and attractive ORN -> DNa, on the MaleCNS edge table with >= 5 synapses
(data/derived/brain_edges_N5.npz = every connection of >= 5 synapses between annotated bodies, plus each body's TRUE total input).
'mass' = linear signed path mass with W[j, i] = sign_i * synapses_ij / total_input_j (whole-connectome input; the sim matrices normalise by in-network input).
python -m flyrun.o0_graph  -> prints the tables, writes flyrun/runs/O0_*.csv and O0_graph.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fly_mario"))
sys.path.insert(0, str(ROOT))
from brain import builder  # noqa: E402

OUT = Path(__file__).resolve().parent / "runs"
d = np.load(ROOT / "data" / "derived" / "brain_edges_N5.npz")
ids, pre, post, w, total_in = d["ids"], d["pre"], d["post"], d["w"].astype(np.float64), d["total_in"]
n = len(ids)
ann = pd.read_feather(ROOT / "data" / "malecns_v1.0" / "body-annotations-male-cns-v1.0-minconf-0.5.feather",
                      columns=["bodyId", "type", "instance", "class", "subclass", "rootSide", "somaSide"]).set_index("bodyId").reindex(ids).reset_index()
side = ann.instance.astype(str).str.extract(r"_([LR])$")[0].fillna(ann.rootSide).fillna(ann.somaSide).fillna("?").to_numpy()
types = ann.type.astype(str).to_numpy().astype("U40")
signs = builder.signs_for(ids)
Wn = sp.csr_matrix((signs[pre] * w / np.maximum(total_in[post], 1.0), (post, pre)), shape=(n, n))   # signed, post x pre
Wc = sp.csr_matrix((w, (post, pre)), shape=(n, n))                                                  # synapse counts, post x pre
res = {}


def idx(mask):
    return np.flatnonzero(mask)


def mass(src, tgt, hops=3):
    """signed linear mass summed over src neurons and tgt neurons, per hop count 1..hops."""
    out = {}
    v = np.zeros(n)
    v[src] = 1.0
    for h in range(1, hops + 1):
        v = Wn @ v
        out[h] = float(v[tgt].sum())
    return out


def by_type(m, k=12):
    return pd.Series(types[m]).value_counts().head(k).to_dict()


# ------------------------------------------------------------------ 1. Johnston's organ
is_jo = np.char.startswith(types, "JO")
sub = ann.subclass.astype(str).to_numpy()
jo_groups = {"JO auditory (subclass auditory)": is_jo & (sub == "auditory"),
             "JO wind/gravity": is_jo & (sub == "wind_gravity"),
             "JO grooming": is_jo & (sub == "grooming"),
             "JO all": is_jo}
tbl = (ann[is_jo].assign(side=side[is_jo]).groupby(["subclass", "type"], dropna=False)
       .agg(n=("bodyId", "size"), L=("side", lambda s: int((s == "L").sum())), R=("side", lambda s: int((s == "R").sum()))).reset_index())
tbl.to_csv(OUT / "O0_jo_types.csv", index=False, lineterminator="\n")
print(tbl.to_string(index=False))
gf = idx(types == "DNp01")
ttmn = idx(types == "TTMn")
print("GF bodies", ids[gf], "TTMn", ids[ttmn])
rows = []
for name, m in {**jo_groups, "LC4": types == "LC4", "LPLC2": types == "LPLC2"}.items():
    s = idx(m)
    direct = Wc[gf][:, s]
    r = dict(source=name, n=len(s), direct_edges=int(direct.nnz), direct_synapses=int(direct.sum()),
             direct_frac_of_GF_input=float(direct.sum() / total_in[gf].sum()))
    ms = mass(s, gf, 3)
    r.update({f"GF_mass_hop{h}": ms[h] for h in (1, 2, 3)})
    mt = mass(s, ttmn, 3)
    r.update({f"TTMn_mass_hop{h}": mt[h] for h in (1, 2, 3)})
    rows.append(r)
cmp = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(cmp.to_string(index=False))
cmp.to_csv(OUT / "O0_jo_vs_looming.csv", index=False, lineterminator="\n")
res["jo_vs_looming"] = rows

aud = idx(jo_groups["JO auditory (subclass auditory)"])
allj = idx(is_jo)
dj = Wc[gf][:, allj].tocoo()
direct = pd.DataFrame({"jo_type": types[allj[dj.col]], "gf_side": side[gf[dj.row]], "syn": dj.data})
print("direct JO->GF (>=5 syn):\n", direct.groupby(["jo_type", "gf_side"]).syn.sum().to_string() if len(direct) else "none")
res["jo_direct_to_GF"] = direct.groupby(["jo_type", "gf_side"]).syn.sum().reset_index().to_dict("records") if len(direct) else []
to_gf_signed = np.asarray(Wn[gf].sum(axis=0)).ravel()          # signed x -> GF
for label, src in (("auditory", aud), ("all", allj)):
    x = np.zeros(n)
    x[src] = 1.0
    mid = Wn @ x                                               # signed J -> x mass
    contrib = mid * to_gf_signed
    contrib[src] = 0
    syn_from = np.asarray(Wc[:, src].sum(axis=1)).ravel()
    syn_to = np.asarray(Wc[gf].sum(axis=0)).ravel()
    df = pd.DataFrame({"type": types, "mass": contrib, "syn_from_JO": syn_from, "syn_to_GF": syn_to})
    df = df[(df.syn_from_JO > 0) & (df.syn_to_GF > 0)]
    top = df.groupby("type").agg(n=("mass", "size"), mass=("mass", "sum"), syn_from_JO=("syn_from_JO", "sum"), syn_to_GF=("syn_to_GF", "sum"))
    top = top.sort_values("mass", key=abs, ascending=False)
    print(f"2-hop JO({label}) -> X -> GF, top intermediate types by |mass|:\n", top.head(12).to_string())
    top.head(30).to_csv(OUT / f"O0_jo_{label}_2hop_types.csv", lineterminator="\n")
    res[f"jo_{label}_2hop_top"] = top.head(12).reset_index().to_dict("records")

st = pd.read_parquet(ROOT / "fly_mario" / "tutorials" / "_cache" / "steer_bodies.parquet")
st_ids = set(st.bodyId.astype(int))
in_steer = np.isin(ids, list(st_ids))
res["jo_in_W_steer"] = int((is_jo & in_steer).sum())
res["orn_in_W_steer"] = int((np.char.startswith(types, "ORN") & in_steer).sum())
print("JO neurons in W_steer:", res["jo_in_W_steer"], " ORN neurons in W_steer:", res["orn_in_W_steer"], " W_steer size", len(st))


def hop_dist(sources, forward=True, k=3):
    M = Wc if forward else Wc.T.tocsr()          # forward: next = M @ front (post rows)
    dist = np.full(n, 99)
    dist[sources] = 0
    front = np.zeros(n)
    front[sources] = 1
    seen = np.zeros(n, bool)
    seen[sources] = True
    for h in range(1, k + 1):
        nxt = ((M @ front) > 0) & ~seen
        dist[nxt] = h
        seen |= nxt
        front = nxt.astype(float)
    return dist


def kn_set(src, tgt, k=3):
    return (hop_dist(src, True, k) + hop_dist(tgt, False, k)) <= k


for label, src in (("auditory JO", aud), ("all JO", allj)):
    keep = kn_set(src, np.concatenate([gf, ttmn]))
    new = keep & ~in_steer
    hd = hop_dist(src, True, 3)
    print(f"k=3,N=5 set {label} -> GF/TTMn: {int(keep.sum())} neurons, {int(new.sum())} not in W_steer; by type:", by_type(new, 15))
    res[f"kN_{label}"] = dict(total=int(keep.sum()), new=int(new.sum()), by_type=by_type(new, 25),
                              by_hop_from_source={int(h): int((hd[new] == h).sum()) for h in (0, 1, 2, 3)})

# ------------------------------------------------------------------ 2. smell
ATTR = ["ORN_DM1", "ORN_VA2", "ORN_DM4"]
dna = {s: idx(np.isin(types, ["DNa01", "DNa02"]) & (side == s)) for s in "LR"}
rows = []
for t in ATTR + ["ATTR all"]:
    for sd in "LR":
        m = (np.isin(types, ATTR) if t == "ATTR all" else types == t) & (side == sd)
        s = idx(m)
        for ds in "LR":
            ms = mass(s, dna[ds], 3)
            rows.append(dict(orn=t, antenna=sd, n=len(s), dna_side=ds, direct_syn=int(Wc[dna[ds]][:, s].sum()), mass_hop2=ms[2], mass_hop3=ms[3]))
orn = pd.DataFrame(rows)
print(orn.to_string(index=False))
orn.to_csv(OUT / "O0_orn_to_dna.csv", index=False, lineterminator="\n")
res["orn_to_dna"] = rows
hrows = []
for sd in "LR":
    s = idx(np.isin(types, ATTR) & (side == sd))
    dist = hop_dist(s, True, 5)
    hrows.append({"antenna": sd, **{f"min_hops_to_DNa_{ds}": int(dist[dna[ds]].min()) for ds in "LR"}})
print(hrows)
res["orn_min_hops"] = hrows
tgt = np.concatenate([dna["L"], dna["R"]])
t_in = np.asarray(Wc[tgt].sum(axis=0)).ravel()
for sd in "LR":
    s = idx(np.isin(types, ATTR) & (side == sd))
    f1 = np.asarray(Wc[:, s].sum(axis=1)).ravel()          # synapses from this antenna's ORNs onto each neuron
    L1 = np.flatnonzero(f1 > 0)
    f2 = np.asarray(Wc[:, L1].sum(axis=1)).ravel()         # onto each neuron from those layer-1 neurons
    cand = np.flatnonzero((f2 > 0) & (t_in > 0))
    best = (pd.DataFrame({"type": types[cand], "from_L1_syn": f2[cand], "to_DNa_syn": t_in[cand]})
            .groupby("type").agg(n=("to_DNa_syn", "size"), from_L1=("from_L1_syn", "sum"), to_DNa=("to_DNa_syn", "sum"))
            .sort_values("to_DNa", ascending=False))
    print(f"antenna {sd}: neurons 2 hops from the ORNs and 1 hop from DNa, top types:\n", best.head(8).to_string())
    res[f"orn_{sd}_chain_top"] = best.head(8).reset_index().to_dict("records")
for sd in "LR":
    s = idx(np.isin(types, ATTR) & (side == sd))
    keep = kn_set(s, tgt)
    new = keep & ~in_steer
    print(f"k=3,N=5 set attractive ORN({sd}) -> DNa: {int(keep.sum())} neurons, {int(new.sum())} not in W_steer; by type:", by_type(new, 12))
    res[f"kN_ORN_{sd}"] = dict(total=int(keep.sum()), new=int(new.sum()), by_type=by_type(new, 25))
keep = kn_set(idx(np.isin(types, ATTR)), tgt)
res["kN_ORN_both"] = dict(total=int(keep.sum()), new=int((keep & ~in_steer).sum()))
print(res["kN_ORN_both"])
json.dump(res, open(OUT / "O0_graph.json", "w"), indent=1, default=float)
