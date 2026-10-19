"""AV1 clips (R3 layout): run the E1 fly on the sour brain with the AV1 toggles, log the rates + CSV, replay the emulator and draw the three panels.
python -m flyrun.av1_clip scene   -> clips/AV1_koopa_scene.mp4   (1-2, replay of arm A to x 780, then the E1 fly with sour + headroom: the x ~ 890 moment)
python -m flyrun.av1_clip full12  -> clips/AV1_12_full.mp4       (1-2 from the start, noop 0 sigma 0, both on)
python -m flyrun.av1_clip still X FRAME   -> clips/AV1_stills/..."""
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
WF = "W_steer_jo_orn_sour.npy"


def log_run(name, level, takeover=None, sour=1, headroom=1):
    os.environ["FLYRUN_LEVEL"] = level
    from . import av1_run as R
    from . import c1_run as C
    from . import env as E
    from .run import run_episode
    if takeover is not None:
        from . import scripted
        scripted.Driver = R.ReplayDriver
    C.WFILE, C.BODIES = WF, R.BODIES[WF]
    C._BRAIN.clear()
    ep = dict(noop_start=0, seed=0, sigma=0.0)
    k, enemy_input = R.knobs_for(sour, headroom, None, 0.0)
    pr = R.Probe12() if level != "1-1" else C.Probe()
    s, df = run_episode(k, R.brain(WF), noop_start=0, episode_seed=0, stuck_frames=150, probe=pr, record_h=True, enemy_input=enemy_input, takeover_x=takeover)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, enemy_input)
    out = C.trace_cols(df)
    out["theta"] = df.theta.round(5)
    out["screen_left"], out["feet_y"] = df.screen_left, df.y
    out["action"] = [E.NAMES.index(b) for b in df.buttons]
    for c in ("hum_block", "smell_box"):
        if c not in df:
            df[c] = None
    out["hum_bottom"] = df.hum_block.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    out["smell_x"] = df.smell_box.map(lambda b: b[0] if isinstance(b, tuple) else np.nan)
    out["smell_top"] = df.smell_box.map(lambda b: b[1] if isinstance(b, tuple) else np.nan)
    out["smell_L"], out["smell_R"] = df.get("smell_L", 0.0), df.get("smell_R", 0.0)
    out["headroom_factor"] = df.headroom_factor.astype(float).round(4)
    out["mdn"] = df.mdn.astype(float).round(5)
    out["sour_box_x_top_w_h"] = df.sour_box.map(lambda b: "" if not isinstance(b, tuple) else " ".join(str(int(v)) for v in b))
    out["flag"] = int(s["flag_get"])
    base = ROOT / "runs" / f"AV1clip_{name}"
    out.to_csv(f"{base}.csv", index=False, lineterminator="\n")
    np.savez_compressed(f"{base}.npz", h=df.attrs["H"].astype(np.float16))
    ov = dict(R.E1_VALUES, SOUR_SENSE=bool(sour), SOUR_GAIN=k.SOUR_GAIN, HEADROOM_LOOM=bool(headroom))
    json.dump(dict(summary=s, toggles=df.attrs["toggles"], arm="C", episode=ep, knob_overrides=ov), open(f"{base}.json", "w"), indent=1, default=float)
    print(name, {a: s[a] for a in ("max_x", "end_reason", "cause", "frames")})
    return base


def write_video(base, path, first=0, fps=60):
    from .render.panels import Log, Renderer
    from .render.video import replay
    lg = Log(base)
    rd = Renderer(lg)
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1920, 1080))
    n = 0
    for k, nes in replay(lg):
        if k >= first:
            vw.write(cv2.cvtColor(rd.frame(nes, k), cv2.COLOR_RGB2BGR))
            n += 1
    vw.release()
    print(path, n, "frames = %.1f s" % (n / fps))


def main():
    what = sys.argv[1]
    (ROOT / "clips").mkdir(exist_ok=True)
    if what == "scene":
        base = log_run("scene", "1-2", takeover=780)
        write_video(base, ROOT / "clips" / "AV1_koopa_scene.mp4", first=500)
    elif what == "full12":
        base = log_run("full12", "1-2")
        write_video(base, ROOT / "clips" / "AV1_12_full.mp4")


if __name__ == "__main__":
    main()
