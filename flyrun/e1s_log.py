"""E1s: log one run of a genome (rates npz + CSV + json, R3-renderable), 1-1 or 1-2 (FLYRUN_LEVEL must be set BEFORE the first emulator use in the process). Modelled on av1_clip.log_run."""
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def log_run(values, name, wfile=None, ep=None, takeover=None, prefix="E1s", brain=None):
    from . import c1_run as C
    from . import e1s_genome as G
    from . import env as E
    from .run import run_episode
    ep = ep or dict(noop_start=0, seed=0, sigma=0.0)
    wfile = wfile or G.WFILE
    level = os.environ.get("FLYRUN_LEVEL", "1-1")
    if takeover is not None:
        from . import av1_run as R
        from . import scripted
        scripted.Driver = R.ReplayDriver
    if brain is None:
        os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, G.BODIES
        from .brain import load_brain
        brain = load_brain()
    C.WFILE, C.BODIES = wfile, G.BODIES
    C._BRAIN.clear()
    C._BRAIN["b"] = brain
    k, enemy_input = G.knobs_for(values)
    import dataclasses
    k = dataclasses.replace(k, SENSOR_NOISE=ep["sigma"])
    from . import av1_run as R
    pr = R.Probe12() if level != "1-1" else C.Probe()
    s, df = run_episode(k, brain, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, record_h=True, enemy_input=enemy_input, takeover_x=takeover)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, enemy_input)
    out = C.trace_cols(df)
    out["theta"] = df.theta.round(5)
    out["screen_left"], out["feet_y"] = df.screen_left, df.y
    out["action"] = [E.NAMES.index(b) for b in df.buttons]
    for c in ("hum_block", "smell_box", "sour_box"):
        if c not in df:
            df[c] = None
    out["hum_bottom"] = df.hum_block.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    out["smell_x"] = df.smell_box.map(lambda b: b[0] if isinstance(b, tuple) else np.nan)
    out["smell_top"] = df.smell_box.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    out["smell_L"], out["smell_R"] = df.get("smell_L", 0.0), df.get("smell_R", 0.0)
    out["headroom_factor"] = df.headroom_factor.astype(float).round(4) if "headroom_factor" in df else 1.0
    out["mdn"] = df.mdn.astype(float).round(5) if "mdn" in df else 0.0
    out["backup"] = df.backup.astype(int) if "backup" in df else 0
    out["sour_level"] = df.sour_level.astype(float).round(4) if "sour_level" in df else 0.0
    out["sour_theta_deg"] = np.degrees(df.sour_theta.astype(float)).round(2) if "sour_theta" in df else 0.0
    out["sour_box_x_top_w_h"] = df.sour_box.map(lambda b: "" if not isinstance(b, tuple) else " ".join(str(int(v)) for v in b))
    out["flag"] = int(s["flag_get"])
    base = ROOT / "runs" / f"{prefix}_{name}"
    out.to_csv(f"{base}.csv", index=False, lineterminator="\n")
    np.savez_compressed(f"{base}.npz", h=df.attrs["H"].astype(np.float16))
    ov = dict(values, SOUR_SENSE=True, HEADROOM_LOOM=True)
    json.dump(dict(summary=s, toggles=df.attrs["toggles"], arm="C", episode=ep, knob_overrides=ov, level=level), open(f"{base}.json", "w"), indent=1, default=float)
    return base, s
