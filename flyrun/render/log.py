"""Run an arm and log what the renderer needs: per-neuron rates (float16 npz), the per-frame CSV (S3e columns + hum / smell / steer / overlay boxes), the soma positions.
No behaviour change: this is c1_run.episode with record_h on."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .. import c1_run as C
from .. import env as E
from ..brain import CACHE

ROOT = Path(__file__).resolve().parents[1]
ANNOT = ROOT.parent.parent / "data" / "malecns_v1.0" / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
EP0 = dict(noop_start=0, seed=0, sigma=0.0)


def soma_all():
    """(bodyId, x, y, z) of every MaleCNS neuron with a soma location (141,781); cached in tutorials/_cache."""
    f = CACHE / "soma_all.npz"
    if f.exists():
        z = np.load(f)
        return z["bodyId"], z["xyz"]
    import pyarrow.feather as pf
    d = pf.read_table(ANNOT, columns=["bodyId", "somaLocation"]).to_pandas().dropna(subset=["somaLocation"])
    xyz = np.stack(d.somaLocation.to_numpy()).astype(np.int32)
    np.savez(f, bodyId=d.bodyId.to_numpy(), xyz=xyz)
    return d.bodyId.to_numpy(), xyz


def run_log(arm, name=None, ep=EP0, max_frames=3000):
    """-> prefix path. Writes runs/R1_<name>.npz (h float16 (frames, neurons), actions), runs/R1_<name>.csv."""
    from ..run import run_episode
    from dataclasses import replace
    k = replace(C.KN, SENSOR_NOISE=ep["sigma"], **C.ARMS[arm])
    pr = C.Probe()
    s, df = run_episode(k, C._brain(), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, max_frames=max_frames, record_h=True)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, True)
    name = name or f"arm{arm}"
    out = C.trace_cols(df)
    out["theta"] = df.theta.round(5)
    out["screen_left"], out["feet_y"] = df.screen_left, df.y
    out["action"] = [E.NAMES.index(b) for b in df.buttons]
    out["hum_bottom"] = df.get("hum_block", pd.Series([None] * len(df))).map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    sb = df.get("smell_box", pd.Series([None] * len(df)))
    out["smell_x"] = sb.map(lambda b: b[0] if isinstance(b, tuple) else np.nan)
    out["smell_top"] = sb.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    out["smell_L"], out["smell_R"] = df.get("smell_L", 0.0), df.get("smell_R", 0.0)
    out["flag"] = int(s["flag_get"])
    base = ROOT / "runs" / f"R1_{name}"
    out.to_csv(f"{base}.csv", index=False, lineterminator="\n")
    np.savez_compressed(f"{base}.npz", h=df.attrs["H"].astype(np.float16))
    json.dump(dict(summary={k_: v for k_, v in s.items()}, toggles=df.attrs["toggles"], arm=arm, episode=ep), open(f"{base}.json", "w"), indent=1, default=float)
    print(name, {k_: s[k_] for k_ in ("max_x", "end_reason", "cause", "frames", "score")})
    return base
