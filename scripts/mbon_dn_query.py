import sys, time
sys.path.insert(0, r"C:\coding\personal\fly_brain")
import numpy as np, pandas as pd
import mcns
t0 = time.time()
ann = mcns.load_annotations()
print("cols", [c for c in ann.columns][:12], flush=True)
ann["type"] = ann["type"].astype(str)
mbon = ann[ann["class"] == "MBON"]
mbon_ids = set(mbon["bodyId"])
groups = {
    "DNp01(GF)": ann["type"].str.fullmatch("DNp01"),
    "DNp02": ann["type"].str.fullmatch("DNp02"),
    "TTMn": ann["type"].str.startswith("TTMn"),
    "GFC1-4": ann["type"].str.match(r"^GFC[1-4]"),
    "DNp09": ann["type"].str.fullmatch("DNp09"),
    "DLMn": ann["type"].str.startswith("DLMn"),
    "MDN": ann["type"].str.fullmatch("MDN"),
    "DNa01": ann["type"].str.fullmatch("DNa01"),
    "DNa02": ann["type"].str.fullmatch("DNa02"),
}
gid = {}
for g, m in groups.items():
    for b in ann.loc[m, "bodyId"]:
        gid[b] = g
print({g: int(m.sum()) for g, m in groups.items()}, "MBON", len(mbon_ids), flush=True)
targets = set(gid)
keep = []
for pre, post, w in mcns._edge_batches():
    m = np.isin(pre, list(mbon_ids)) | np.isin(post, list(targets))
    if m.any():
        keep.append(pd.DataFrame({"pre": pre[m], "post": post[m], "w": w[m]}))
E = pd.concat(keep, ignore_index=True)
print("edges kept", len(E), "secs", time.time() - t0, flush=True)
mb_out = E[E.pre.isin(mbon_ids)]
direct = mb_out[mb_out.post.isin(targets)].copy()
direct["group"] = direct.post.map(gid)
print("\nDIRECT MBON -> target (synapses):")
print(direct.groupby("group")["w"].agg(["sum", "count"]).to_string())
# 2-hop: MBON -> X -> target
mid = mb_out.groupby("post")["w"].sum()
into_t = E[E.post.isin(targets) & ~E.pre.isin(mbon_ids)].copy()
into_t["group"] = into_t.post.map(gid)
j = into_t.merge(mb_out[["post", "w"]].rename(columns={"post": "pre", "w": "w1"}), on="pre")
j = j.groupby(["group", "pre"]).agg(w1=("w1", "sum"), w2=("w", "sum")).reset_index()
j["path"] = j.w1.astype(float) * j.w2 / 1.0
ann_i = ann.set_index("bodyId")
j["mid_type"] = j.pre.map(ann_i["type"])
j["mid_class"] = j.pre.map(ann_i["class"])
print("\nTWO-HOP MBON -> X -> target: per target group (n intermediates, sum w2 = X->target synapses, sum w1 = MBON->X synapses)")
print(j.groupby("group").agg(n_mid=("pre", "nunique"), mbon_to_x=("w1", "sum"), x_to_target=("w2", "sum")).to_string())
print("\nTop intermediates per group (by min(w1,w2)):")
j["m"] = np.minimum(j.w1, j.w2)
for g, d in j.groupby("group"):
    print(g, d.sort_values("m", ascending=False).head(4)[["mid_type", "mid_class", "w1", "w2"]].to_string(index=False, header=False).replace("\n", " | "))
# MBON types with direct edges
d2 = direct.copy()
d2["mbon_type"] = d2.pre.map(ann_i["type"])
print("\nDirect edges by MBON type -> group (sum):")
print(d2.groupby(["group", "mbon_type"])["w"].sum().sort_values(ascending=False).head(15).to_string())
# MBON outputs onto any descending neuron
dn = set(ann.loc[ann["class"].astype(str).str.contains("descending", case=False) | ann["superclass"].astype(str).str.contains("descending", case=False), "bodyId"])
dd = mb_out[mb_out.post.isin(dn)]
print("\nMBON -> ANY descending neuron: synapses", int(dd.w.sum()), "DNs reached", dd.post.nunique(), flush=True)
print("secs", time.time() - t0)
