"""Part O0, sections 1-2 (scratch simulations): W_steer + JO / ORN additions built by the project's k/N rule, driven directly.
The default brain (tutorials/_cache/W_steer.npy) is NOT touched: every build here lives in memory.
Rows of the base 636 neurons keep their W_steer edges (all weights); an edge with a NEW endpoint is kept if it has >= 5 synapses (N = 5, the rule);
each row is normalised by its in-network input (the W_steer recipe), signed by the presynaptic transmitter.
python -m flyrun.o0_sim  -> prints the tables, writes flyrun/runs/O0_sim.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fly_mario"))
sys.path.insert(0, str(ROOT))
from brain import builder  # noqa: E402

OUT = Path(__file__).resolve().parent / "runs"
CACHE = ROOT / "fly_mario" / "tutorials" / "_cache"
G, ALPHA, CLIP, SUBSTEPS = 0.5, 0.3, 50.0, 10       # the Knobs defaults used by every run
TTMN_THRESH, HOME_R, DNP09_THRESH, STEER_THRESH = 0.10, 0.5, 0.05, 0.01

d = np.load(ROOT / "data" / "derived" / "brain_edges_N5.npz")
IDS, PRE, POST, WSYN, TOTAL_IN = d["ids"], d["pre"], d["post"], d["w"].astype(np.float64), d["total_in"]
ann = pd.read_feather(ROOT / "data" / "malecns_v1.0" / "body-annotations-male-cns-v1.0-minconf-0.5.feather",
                      columns=["bodyId", "type", "instance", "subclass", "rootSide", "somaSide"]).set_index("bodyId").reindex(IDS).reset_index()
SIDE = ann.instance.astype(str).str.extract(r"_([LR])$")[0].fillna(ann.rootSide).fillna(ann.somaSide).fillna("?").to_numpy()
TYPES = ann.type.astype(str).to_numpy().astype("U40")
SIGNS = builder.signs_for(IDS)
ST = pd.read_parquet(CACHE / "steer_bodies.parquet")
ST_E = pd.read_parquet(CACHE / "steer_edges.parquet")


def build(extra_ids):
    """-> (W, bodies DataFrame[bodyId, type, side, sign]) for W_steer + extra_ids (annotated bodyIds not already in W_steer)."""
    base = ST.bodyId.to_numpy(np.int64)
    extra = np.array([b for b in extra_ids if b not in set(base.tolist())], dtype=np.int64)
    order = np.concatenate([base, extra])
    K = len(order)
    pos = {int(b): i for i, b in enumerate(order)}
    Wc = np.zeros((K, K))
    for r in ST_E.itertuples(index=False):                      # base <-> base: all-weight edges, as W_steer
        a, b = int(r.body_pre), int(r.body_post)
        if a in pos and b in pos and pos[a] < len(base) and pos[b] < len(base):
            Wc[pos[b], pos[a]] += r.weight
    ii = np.searchsorted(IDS, order)
    new = np.zeros(len(IDS), bool)
    new[ii[len(base):]] = True
    inn = np.zeros(len(IDS), bool)
    inn[ii] = True
    m = inn[PRE] & inn[POST] & (new[PRE] | new[POST])           # any edge with a new endpoint (>= 5 synapses by construction)
    loc = np.full(len(IDS), -1)
    loc[ii] = np.arange(K)
    np.add.at(Wc, (loc[POST[m]], loc[PRE[m]]), WSYN[m])
    sign = np.concatenate([ST.sign.to_numpy(float), SIGNS[ii[len(base):]]])
    rs = Wc.sum(1, keepdims=True)
    W = np.divide(Wc, rs, out=np.zeros_like(Wc), where=rs > 0) * sign[None, :]
    side = np.concatenate([ST.somaSide.fillna("").to_numpy(), SIDE[ii[len(base):]]])
    typ = np.concatenate([ST.type.to_numpy().astype(str), TYPES[ii[len(base):]]])
    return W, pd.DataFrame(dict(bodyId=order, type=typ, side=side))


def kn_new_ids(src_mask, tgt_mask, k=3):
    """The k/N set (every neuron on a <= k-hop walk of >= 5-synapse edges from sources to targets), as bodyIds."""
    import scipy.sparse as sp
    n = len(IDS)
    Wc = sp.csr_matrix((WSYN, (POST, PRE)), shape=(n, n))

    def dist(src, fwd):
        M = Wc if fwd else Wc.T.tocsr()
        dd = np.full(n, 99)
        dd[src] = 0
        fr = np.zeros(n)
        fr[src] = 1
        seen = np.zeros(n, bool)
        seen[src] = True
        for h in range(1, k + 1):
            nx = ((M @ fr) > 0) & ~seen
            dd[nx] = h
            seen |= nx
            fr = nx.astype(float)
        return dd
    keep = (dist(np.flatnonzero(src_mask), True) + dist(np.flatnonzero(tgt_mask), False)) <= k
    return IDS[keep]


class Net:
    def __init__(self, W, bodies):
        self.W, self.b = W, bodies
        self.K = len(bodies)
        t, s = bodies.type.to_numpy(), bodies.side.to_numpy()
        self.m = {"LC4_R": (t == "LC4") & (s == "R"), "LPLC2_R": (t == "LPLC2") & (s == "R"), "LC10a_R": (t == "LC10a") & (s == "R"),
                  "GF": t == "DNp01", "TTMn": t == "TTMn", "DNp09": t == "DNp09",
                  "DNa_L": np.isin(t, ["DNa01", "DNa02"]) & (s == "L"), "DNa_R": np.isin(t, ["DNa01", "DNa02"]) & (s == "R")}

    def run(self, I_of_t, frames):
        """-> dict of per-frame mean activities; I_of_t(frame) -> input vector."""
        h = np.zeros(self.K)
        tr = {k: [] for k in ("GF", "TTMn", "DNp09", "DNa_L", "DNa_R")}
        for f in range(frames):
            I = I_of_t(f)
            for _ in range(SUBSTEPS):
                h = (1 - ALPHA) * h + ALPHA * np.clip(G * (self.W @ h) + I, 0.0, CLIP)
            for k in tr:
                tr[k].append(float(h[self.m[k]].mean()))
        return {k: np.array(v) for k, v in tr.items()}

    def vec(self, **named):
        I = np.zeros(self.K)
        for k, v in named.items():
            I[self.m[k]] = v
        return I


def onset_inputs():
    """The looming input at the fly's trigger: median (theta, dtheta) at grounded A onsets on enemies / faces in the S3e smoke run."""
    df = pd.read_csv(OUT / "S3e_smoke_log.csv")
    on = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0) & (df.air == 0) & df.threat_kind.isin(["goomba", "koopa", "face"]) & (df.stim_d >= 5)]
    return float(on.theta.median()), float(on.dtheta.median()), len(on), df


def main():
    res = {}
    th, dth, n_on, smoke = onset_inputs()
    print(f"trigger input: theta {np.degrees(th):.1f} deg ({th:.3f} rad), dtheta {dth:.4f} rad/frame, from {n_on} onsets")
    res["trigger"] = dict(theta_deg=float(np.degrees(th)), theta_rad=th, dtheta=dth, n_onsets=n_on)
    jo_all = (np.char.startswith(TYPES, "JO"))
    aud = jo_all & (ann.subclass.astype(str).to_numpy() == "auditory")
    gfm = TYPES == "DNp01"
    # the smallest additions: (a) the JO neurons with a >= 5-synapse edge straight onto GF; (b) the full k=3,N=5 set from auditory JO
    direct_mask = np.zeros(len(IDS), bool)
    sel = gfm[POST] & jo_all[PRE]
    direct_mask[PRE[sel]] = True
    jo20 = IDS[direct_mask]
    kn_aud = kn_new_ids(aud, gfm | (TYPES == "TTMn"))
    print("direct JO -> GF neurons:", len(jo20), pd.Series(TYPES[direct_mask]).value_counts().to_dict(), "| k/N auditory set:", len(kn_aud))
    res["jo_direct"] = dict(n=len(jo20), by_type=pd.Series(TYPES[direct_mask]).value_counts().to_dict())
    nets = {"W_steer (default)": Net(*build([])),
            "+ direct JO (the smallest addition)": Net(*build(list(jo20))),
            "+ k=3,N=5 auditory JO set": Net(*build(list(kn_aud)))}
    for k, net in nets.items():
        print(k, "K =", net.K)
    # --- looming reference: replay the smoke run's Goomba-1 approach (theta, dtheta per frame up to the first press)
    onset = int(smoke.index[(smoke.a == 1) & (smoke.a.shift(1, fill_value=0) == 0)][0])
    app = smoke.iloc[100:onset + 1]
    refs = {}
    for k, net in nets.items():
        tr = net.run(lambda f: net.vec(LPLC2_R=float(app.theta.iloc[min(f, len(app) - 1)]), LC4_R=float(app.dtheta.iloc[min(f, len(app) - 1)]), LC10a_R=HOME_R), len(app))
        cross = np.flatnonzero(tr["TTMn"] >= TTMN_THRESH)
        refs[k] = dict(GF_peak=float(tr["GF"].max()), TTMn_peak=float(tr["TTMn"].max()), crossed_at_frame=int(cross[0]) if len(cross) else None, frames=len(app),
                       first_press_frame=len(app) - 1)
        st = net.run(lambda f: net.vec(LPLC2_R=th, LC4_R=dth, LC10a_R=HOME_R), 120)
        refs[k].update(steady_GF=float(st["GF"][-1]), steady_TTMn=float(st["TTMn"][-1]))
    print("looming reference (replay of the approach to the first Goomba, then a steady input at the trigger):")
    print(pd.DataFrame(refs).T.to_string())
    res["looming_ref"] = refs
    # --- JO alone
    jo_sets = {"auditory JO": aud, "all JO": jo_all}
    rows = []
    n_aud = {}
    for k, net in list(nets.items())[1:]:
        for sname, smask in jo_sets.items():
            idx = np.flatnonzero(np.isin(net.b.bodyId.to_numpy(), IDS[smask]))
            if not len(idx) or (sname == 'all JO' and len(idx) == n_aud[k]):
                continue
            n_aud[k] = len(idx) if sname == 'auditory JO' else n_aud.get(k)
            for lvl in (1, 2, 5, 10, 20, 50):
                I = np.zeros(net.K)
                I[idx] = lvl
                tr = net.run(lambda f: I, 100)
                rows.append(dict(build=k, driven=sname, n_driven=len(idx), level=lvl, GF_peak=tr["GF"].max(), TTMn_peak=tr["TTMn"].max(), TTMn_ge_thr=bool(tr["TTMn"].max() >= TTMN_THRESH),
                                 DNp09_peak=tr["DNp09"].max()))
            lo, hi = 0.0, 1000.0                       # the smallest uniform level at which TTMn reaches the threshold (None if not even at 1000)
            I = np.zeros(net.K); I[idx] = hi
            if net.run(lambda f: I, 100)["TTMn"].max() < TTMN_THRESH:
                rows.append(dict(build=k, driven=sname, n_driven=len(idx), level="min level reaching thr", GF_peak=np.nan, TTMn_peak=np.nan, TTMn_ge_thr=False, DNp09_peak=np.nan))
                continue
            for _ in range(14):
                mid = (lo + hi) / 2
                I = np.zeros(net.K); I[idx] = mid
                lo, hi = (lo, mid) if net.run(lambda f: I, 100)["TTMn"].max() >= TTMN_THRESH else (mid, hi)
            rows.append(dict(build=k, driven=sname, n_driven=len(idx), level=f"min level reaching thr = {hi:.2f}", GF_peak=np.nan, TTMn_peak=np.nan, TTMn_ge_thr=True, DNp09_peak=np.nan))
    jt = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print(jt.to_string(index=False))
    jt.to_csv(OUT / "O0_jo_drive.csv", index=False, lineterminator="\n")
    res["jo_drive"] = rows
    # --- smell -> steering
    ATTR = ["ORN_DM1", "ORN_VA2", "ORN_DM4"]
    orn_mask = np.isin(TYPES, ATTR)
    dna = np.isin(TYPES, ["DNa01", "DNa02"])
    kn_orn = kn_new_ids(orn_mask, dna)
    net = Net(*build(list(kn_orn)))
    print("W_steer + k=3,N=5 attractive-ORN -> DNa set:", len(kn_orn), "neurons, K =", net.K)
    res["orn_build"] = dict(n_added=len(kn_orn), K=net.K, by_type=pd.Series(TYPES[np.isin(IDS, kn_orn)]).value_counts().head(12).to_dict())
    rows = []
    for ant in "LR":
        idx = np.flatnonzero(np.isin(net.b.bodyId.to_numpy(), IDS[orn_mask & (SIDE == ant)]))
        for lvl in (1, 2, 5, 10, 20, 50):
            I = np.zeros(net.K)
            I[idx] = lvl
            tr = net.run(lambda f: I, 100)
            steer = tr["DNa_R"] - tr["DNa_L"]
            rows.append(dict(antenna=ant, n_driven=len(idx), level=lvl, DNa_L_peak=tr["DNa_L"].max(), DNa_R_peak=tr["DNa_R"].max(), steer_RminusL_final=steer[-1],
                             steer_min=steer.min(), steer_max=steer.max(), DNp09_peak=tr["DNp09"].max()))
    ot = pd.DataFrame(rows)
    print(ot.to_string(index=False))
    # the same build under the looming replay and under HOME_R alone / HOME_R + a left-antenna ORN drive (the M2 balance)
    tr = net.run(lambda f: net.vec(LPLC2_R=float(app.theta.iloc[min(f, len(app) - 1)]), LC4_R=float(app.dtheta.iloc[min(f, len(app) - 1)]), LC10a_R=HOME_R), len(app))
    res["orn_build_looming_TTMn_peak"] = float(tr["TTMn"].max())
    print("ORN build: looming replay TTMn peak", tr["TTMn"].max(), "(default 0.1033)")
    rows = []
    idxL = np.flatnonzero(np.isin(net.b.bodyId.to_numpy(), IDS[orn_mask & (SIDE == "L")]))
    for lvl in (0, 1, 2, 5, 10, 20, 50):
        I = net.vec(LC10a_R=HOME_R)
        I[idxL] = lvl
        t2 = net.run(lambda f: I, 100)
        rows.append(dict(HOME_R=HOME_R, left_ORN_level=lvl, DNp09=t2["DNp09"][-1], DNa_L=t2["DNa_L"][-1], DNa_R=t2["DNa_R"][-1], steer_RminusL=t2["DNa_R"][-1] - t2["DNa_L"][-1]))
    hb = pd.DataFrame(rows)
    print("HOME_R on, left antenna ORNs added:")
    print(hb.to_string(index=False))
    hb.to_csv(OUT / "O0_home_vs_smell.csv", index=False, lineterminator="\n")
    res["home_vs_smell"] = rows
    ot.to_csv(OUT / "O0_orn_drive.csv", index=False, lineterminator="\n")
    res["orn_drive"] = rows
    # cross-check with the existing thin-bridge cast (tutorials/_cache W_odour: the 21_odour notebook), left antenna only
    ob = pd.read_parquet(CACHE / "odour_bodies.parquet")
    Wo = np.load(CACHE / "W_odour.npy")
    a2 = ann.set_index("bodyId")
    sd = np.array([("L" if str(a2.instance.get(b, "")).endswith("_L") else "R" if str(a2.instance.get(b, "")).endswith("_R") else (str(ob.somaSide.iloc[i]) if "somaSide" in ob else "?")) if (str(ob.type.iloc[i]).startswith("ORN") or ob.type.iloc[i] in ("DM1_lPN", "VA2_adPN", "DM4_adPN", "DM4_vPN")) else (str(ob.somaSide.iloc[i]) if "somaSide" in ob else "?") for i, b in enumerate(ob.bodyId)])
    no = Net(Wo, pd.DataFrame(dict(bodyId=ob.bodyId.to_numpy(), type=ob.type.to_numpy().astype(str), side=np.where(pd.isna(ob.somaSide), "", ob.somaSide) if "somaSide" in ob else sd)))
    no.b["side"] = [s if t.startswith("ORN") is False else sd[i] for i, (s, t) in enumerate(zip(no.b.side, no.b.type))]
    no.m = Net(Wo, no.b).m
    rows = []
    for ant in "LR":
        idx = np.flatnonzero((no.b.type.str.startswith("ORN")) & (no.b.side == ant))
        for lvl in (5, 20, 50):
            I = np.zeros(no.K)
            I[idx] = lvl
            tr = no.run(lambda f: I, 100)
            st = tr["DNa_R"] - tr["DNa_L"]
            rows.append(dict(cast="W_odour (21_odour thin bridge)", antenna=ant, n_driven=len(idx), level=lvl, steer_RminusL_final=st[-1], DNa_L_peak=tr["DNa_L"].max(), DNa_R_peak=tr["DNa_R"].max()))
    print(pd.DataFrame(rows).to_string(index=False))
    res["orn_drive_W_odour"] = rows
    json.dump(res, open(OUT / "O0_sim.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
