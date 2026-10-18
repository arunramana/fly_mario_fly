"""JO / ORN neurons have no soma in MaleCNS (their cell bodies are in the antenna). The local data has no synapse coordinates either, so each one is drawn at the synapse-weighted mean position of the
somata of its POSTSYNAPTIC partners that lie in the brain (z < 50k): JO -> the AMMC neurons they feed, ORNs -> the PNs / LNs of their glomeruli (DM1, VA2, DM4). A proxy for "the mean position of its output
synapses", always inside the brain. Streams the 152M-row weights file once; cached in tutorials/_cache/sensory_pos.npz.
python -m flyrun.render.sensory"""
import numpy as np
import pyarrow as pa

from ..brain import CACHE
from . import log as L

WEIGHTS = L.ANNOT.parent / "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
BRAIN_Z_MAX = 50000


def positions(body_ids):
    """-> (n, 3) float array of voxel coordinates (x, y, z), one row per body id."""
    f = CACHE / "sensory_pos.npz"
    body_ids = np.asarray(body_ids, dtype=np.int64)
    if f.exists():
        z = np.load(f)
        if np.array_equal(z["bodyId"], body_ids):
            return z["xyz"]
    aid, axyz = L.soma_all()
    order = np.argsort(aid)
    sid, sxyz = aid[order], axyz[order].astype(np.float64)
    acc = {int(b): np.zeros(4) for b in body_ids}
    src = pa.memory_map(str(WEIGHTS))
    rd = pa.ipc.open_file(src)
    ids = np.sort(body_ids)
    for i in range(rd.num_record_batches):
        b = rd.get_batch(i)
        pre = b.column("body_pre").to_numpy()
        m = np.isin(pre, ids)
        if not m.any():
            continue
        post, w = b.column("body_post").to_numpy()[m], b.column("weight").to_numpy()[m].astype(np.float64)
        pre = pre[m]
        j = np.searchsorted(sid, post)
        j = np.clip(j, 0, len(sid) - 1)
        ok = (sid[j] == post) & (sxyz[j, 2] < BRAIN_Z_MAX)
        for p, jj, ww in zip(pre[ok], j[ok], w[ok]):
            a = acc[int(p)]
            a[:3] += ww * sxyz[jj]
            a[3] += ww
    xyz = np.array([acc[int(b)][:3] / acc[int(b)][3] if acc[int(b)][3] > 0 else [np.nan] * 3 for b in body_ids])
    np.savez(f, bodyId=body_ids, xyz=xyz)
    return xyz


if __name__ == "__main__":
    from ..c1_run import _brain
    import os
    os.environ.setdefault("FLYRUN_WFILE", "W_steer_jo_orn.npy")
    b = _brain().bodies
    m = b.type.astype(str).str.startswith(("JO", "ORN"))
    p = positions(b.bodyId[m].to_numpy())
    print(len(p), "nan:", int(np.isnan(p[:, 0]).sum()), p[~np.isnan(p[:, 0])].mean(0), p[~np.isnan(p[:, 0])].min(0), p[~np.isnan(p[:, 0])].max(0))
