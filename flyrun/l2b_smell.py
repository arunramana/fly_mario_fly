"""Part L2b section 3: the AVERSIVE smell wiring check (graph facts + scratch build, like O0). Nothing here changes the production brain: every build lives in memory.
Candidate aversive ORN channels (literature, MaleCNS type names): ORN_V (Gr21a/Gr63a, CO2), ORN_DA2 (Or56a, geosmin), ORN_DL5 (Or7a, alkenals / aversive in Strutz 2014),
ORN_DA4l / VL2p are NOT included (mixed valence). Same tools as O0 (k = 3, N = 5 rule, row-normalised signed counts, steer = mean DNa_R - mean DNa_L).
python -m flyrun.l2b_smell  -> prints, writes runs/L2b_smell.json, runs/L2b_smell_drive.csv"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import o0_sim as S

OUT = Path(__file__).resolve().parent / "runs"
ID, TYPES, SIDE = S.IDS, S.TYPES, S.SIDE
n = len(ID)
Wc = sp.csr_matrix((S.WSYN, (S.POST, S.PRE)), shape=(n, n))
Wn = sp.csr_matrix((S.SIGNS[S.PRE] * S.WSYN / np.maximum(S.TOTAL_IN[S.POST], 1.0), (S.POST, S.PRE)), shape=(n, n))
DNA = np.isin(TYPES, ["DNa01", "DNa02"])
dna = {s: np.flatnonzero(DNA & (SIDE == s)) for s in "LR"}
SETS = {"V": ["ORN_V"], "DA2": ["ORN_DA2"], "DL5": ["ORN_DL5"], "V+DA2": ["ORN_V", "ORN_DA2"], "V+DA2+DL5": ["ORN_V", "ORN_DA2", "ORN_DL5"], "ATTR (in the model)": ["ORN_DM1", "ORN_VA2", "ORN_DM4"]}
res = {}


def hops(src, k=5):
    dist = np.full(n, 99)
    dist[src] = 0
    fr = np.zeros(n); fr[src] = 1
    seen = np.zeros(n, bool); seen[src] = True
    for h in range(1, k + 1):
        nx = ((Wc @ fr) > 0) & ~seen
        dist[nx] = h
        seen |= nx
        fr = nx.astype(float)
    return dist


def mass(src, tgt, hmax=3):
    v = np.zeros(n); v[src] = 1.0
    out = {}
    for h in range(1, hmax + 1):
        v = Wn @ v
        out[h] = float(v[tgt].sum())
    return out


# ---- 1. counts
rows = []
for t in ["ORN_V", "ORN_DA2", "ORN_DL5", "ORN_DM1", "ORN_VA2", "ORN_DM4"]:
    m = TYPES == t
    rows.append(dict(type=t, L=int((m & (SIDE == "L")).sum()), R=int((m & (SIDE == "R")).sum()), other=int((m & ~np.isin(SIDE, ["L", "R"])).sum()), in_N5_graph=int(m.sum())))
cnt = pd.DataFrame(rows)
print(cnt.to_string(index=False))
res["counts"] = rows

# ---- 2. path to DNa
st_ids = set(S.ST.bodyId.astype(int))
cur = pd.read_parquet(S.CACHE / "steer_jo_orn_bodies.parquet")
cur_ids = set(cur.bodyId.astype(int))
rows = []
for name, tl in SETS.items():
    for ant in "LR":
        s = np.flatnonzero(np.isin(TYPES, tl) & (SIDE == ant))
        d = hops(s)
        r = dict(set=name, antenna=ant, n_orn=len(s), in_model=int(np.isin(ID[s], list(cur_ids)).sum()))
        for ds in "LR":
            r[f"direct_syn_DNa_{ds}"] = int(Wc[dna[ds]][:, s].sum())
            r[f"min_hops_DNa_{ds}"] = int(d[dna[ds]].min())
            m = mass(s, dna[ds], 3)
            r[f"mass_h2_DNa_{ds}"], r[f"mass_h3_DNa_{ds}"] = m[2], m[3]
        rows.append(r)
pt = pd.DataFrame(rows)
pd.set_option("display.width", 250, "display.max_columns", 30)
print(pt.to_string(index=False))
res["paths"] = rows
pt.to_csv(OUT / "L2b_smell_paths.csv", index=False, lineterminator="\n")

# ---- 2b. which neurons carry it: the hop-2 layer (ORN -> X -> Y -> DNa), signed mass by type, for each antenna of V and of DA2
carry = {}
for name in ("V", "DA2"):
    for ant in "LR":
        s0 = np.flatnonzero(np.isin(TYPES, SETS[name]) & (SIDE == ant))
        x = np.zeros(n); x[s0] = 1.0
        v2 = Wn @ (Wn @ x)                       # signed mass reaching each neuron after 2 hops
        for ds in "LR":
            into = np.asarray(Wn[dna[ds]].sum(axis=0)).ravel()   # that neuron's signed weight onto DNa side ds
            c = v2 * into
            df_ = pd.DataFrame({"type": TYPES, "mass": c, "side": SIDE})
            top = df_[df_.mass != 0].groupby("type").mass.sum().sort_values(key=abs, ascending=False).head(5)
            carry[f"{name}_{ant}->DNa_{ds}"] = {k: float(v) for k, v in top.items()}
            print(f"{name} {ant} antenna -> DNa_{ds}: hop-2 carriers (type: signed mass)", {k: f"{v:.2e}" for k, v in top.items()})
res["carriers"] = carry

# ---- 3. k/N additions beyond the current 881-neuron brain
adds = {}
for name, tl in SETS.items():
    if name.startswith("ATTR"):
        continue
    kn = [int(b) for b in S.kn_new_ids(np.isin(TYPES, tl), DNA)]
    new = [b for b in kn if b not in cur_ids]
    orn_new = [b for b in new if TYPES[np.searchsorted(ID, b)].startswith("ORN")]
    inter_new = [b for b in new if b not in set(orn_new)]
    adds[name] = new
    bytype = pd.Series(TYPES[np.searchsorted(ID, inter_new)]).value_counts().head(10).to_dict() if inter_new else {}
    print(f"{name}: k/N set {len(kn)}; not in the 881 brain: {len(new)} = {len(orn_new)} ORNs + {len(inter_new)} intermediates (of which already in model: {len(kn) - len(new)}); intermediates by type: {bytype}")
    res.setdefault("kN", {})[name] = dict(total=len(kn), new=len(new), new_orns=len(orn_new), new_intermediates=len(inter_new), by_type=bytype)

# ---- 4. scratch build + drive
extra_cur = [int(b) for b in cur.bodyId if int(b) not in st_ids]
LEV = (0, 1, 2, 5, 10, 15, 20, 30, 40, 45, 50, 60)


def drive(name, tl):
    net = S.Net(*S.build(extra_cur + adds[name]))
    ids = net.b.bodyId.to_numpy()
    out = []
    for ant in "LR":
        idx = np.flatnonzero(np.isin(ids, ID[np.isin(TYPES, tl) & (SIDE == ant)]))
        for home in (S.HOME_R, 0.0):
            for lvl in LEV:
                I = net.vec(LC10a_R=home)
                I[idx] = lvl
                tr = net.run(lambda f: I, 100)
                out.append(dict(build=name, K=net.K, antenna=ant, n_driven=len(idx), home_R=home, level=lvl, DNa_L=tr["DNa_L"][-1], DNa_R=tr["DNa_R"][-1], steer_RminusL=tr["DNa_R"][-1] - tr["DNa_L"][-1],
                                DNp09=tr["DNp09"][-1], TTMn_peak=tr["TTMn"].max(), GF_peak=tr["GF"].max()))
    return net, out


allrows = []
# reference: the attractive build as it is now (the production 881 brain, no additions)
net0 = S.Net(*S.build(extra_cur))
ids0 = net0.b.bodyId.to_numpy()
for ant in "LR":
    idx = np.flatnonzero(np.isin(ids0, ID[np.isin(TYPES, SETS["ATTR (in the model)"]) & (SIDE == ant)]))
    for lvl in (0, 20, 50):
        I = net0.vec(LC10a_R=S.HOME_R); I[idx] = lvl
        tr = net0.run(lambda f: I, 100)
        allrows.append(dict(build="881 brain, attractive ORNs", K=net0.K, antenna=ant, n_driven=len(idx), home_R=S.HOME_R, level=lvl, DNa_L=tr["DNa_L"][-1], DNa_R=tr["DNa_R"][-1],
                            steer_RminusL=tr["DNa_R"][-1] - tr["DNa_L"][-1], DNp09=tr["DNp09"][-1], TTMn_peak=tr["TTMn"].max(), GF_peak=tr["GF"].max()))
for name in ("V", "DA2", "V+DA2", "V+DA2+DL5"):
    net, rows = drive(name, SETS[name])
    allrows += rows
# ---- 5. the smallest V addition: drop V's intermediates greedily (least influential first) while the right-antenna steer at level 20 and 50 stays within 10 % (M2's rule)
def steer_V(extra, ant, lvl):
    net = S.Net(*S.build(extra_cur + extra))
    idx = np.flatnonzero(np.isin(net.b.bodyId.to_numpy(), ID[np.isin(TYPES, ["ORN_V"]) & (SIDE == ant)]))
    I = net.vec(LC10a_R=S.HOME_R); I[idx] = lvl
    tr = net.run(lambda f: I, 100)
    return float(tr["DNa_R"][-1] - tr["DNa_L"][-1])


vnew = adds["V"]
orn_ids = {b for b in vnew if TYPES[np.searchsorted(ID, b)].startswith("ORN")}
vint = [b for b in vnew if b not in orn_ids]
ref = {l: steer_V(vnew, "R", l) for l in (20, 50)}
keep = list(vnew)
for b in sorted(vint, key=lambda b: sum(abs(steer_V([x for x in vnew if x != b], "R", l) - ref[l]) for l in (20, 50))):
    trial = [x for x in keep if x != b]
    if all(abs(steer_V(trial, "R", l) - ref[l]) <= 0.1 * abs(ref[l]) for l in (20, 50)):
        keep = trial
kept_int = [b for b in keep if b not in orn_ids]
print("V smallest set:", len(keep), "=", len(orn_ids), "ORNs +", len(kept_int), "intermediates:", pd.Series(TYPES[np.searchsorted(ID, kept_int)]).value_counts().to_dict() if kept_int else {},
      "| right antenna steer at 20 / 50 (full, pruned):", [round(ref[l], 4) for l in (20, 50)], [round(steer_V(keep, "R", l), 4) for l in (20, 50)])
res["V_smallest"] = dict(n=len(keep), orns=len(orn_ids), intermediates=len(kept_int), types=pd.Series(TYPES[np.searchsorted(ID, kept_int)]).value_counts().to_dict() if kept_int else {},
                         steer_R_full=ref, steer_R_pruned={l: steer_V(keep, "R", l) for l in (20, 50)})

df = pd.DataFrame(allrows)
df.to_csv(OUT / "L2b_smell_drive.csv", index=False, lineterminator="\n")
print(df[(df.antenna == "R") & (df.level.isin([0, 1, 5, 20, 50, 60]))][["build", "K", "home_R", "level", "DNa_L", "DNa_R", "steer_RminusL", "DNp09", "TTMn_peak"]].to_string(index=False))
res["drive"] = allrows
json.dump(res, open(OUT / "L2b_smell.json", "w"), indent=1, default=float)
