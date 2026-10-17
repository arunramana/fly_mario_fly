"""Part P: clips/P_current_death.mp4 = the 7e final genome on HOLDOUT ep0 (noop 3, seed 101, sigma 0), from x~1400 to its death,
played at 30 fps (= 0.5x of the 60 Hz game) with an x / stim / TTMn / A overlay. Re-renders a logged episode (not a new HOLDOUT
evaluation); asserts the replay's max_x equals the one logged in runs/008e_holdout.json."""
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from . import part7 as P
from .brain import load_brain
from .diagnose7b import capture
from .diagnose_f1 import ADDR_ESTATE, ADDR_PSTATE, ADDR_YSPEED
from . import env as E

ROOT = Path(__file__).resolve().parent


def main(out_name="P_current_death.mp4", title="7e final genome - HOLDOUT noop 3, sigma 0"):
    cfg = P.load_config(ROOT / "configs" / "part7.yaml")
    g = json.loads((ROOT / "runs" / "008e_final_genome.json").read_text(encoding="utf-8"))
    knobs, genome = P.decode(cfg, g["u"])
    assert genome == g["genome"]
    ep = cfg["episodes"]["holdout"][0]
    logged = json.loads((ROOT / "runs" / "008e_holdout.json").read_text(encoding="utf-8"))["final"]["episodes"][0]
    def extra(ram):
        ys = int(ram[ADDR_YSPEED])
        return (int(ram[ADDR_PSTATE]), ys - 256 if ys > 127 else ys,
                " ".join(f"s{k}:st{int(ram[ADDR_ESTATE + k]):02X}" for k in range(E.N_ENEMY_SLOTS)
                         if int(ram[E.ADDR_ENEMY_ACTIVE + k]) and int(ram[E.ADDR_ENEMY_TYPE + k]) != E.POWERUP_ID))
    s, d = capture(replace(knobs, SENSOR_NOISE=float(ep["sigma"])), ep, load_brain(), record=True, extra=extra)
    assert s["max_x"] == logged["max_x"], (s["max_x"], logged["max_x"])
    frames, thr = d.attrs["frames"], knobs.TTMN_THRESH
    lo = int(d[d.x >= 1400].frame.iloc[0])
    hi = len(d) - 1
    assert (hi - lo + 1) / 2 / 30 <= 20, "clip would exceed 20 s"
    S = 3
    h, w = frames[0].shape[:2]
    out = ROOT / "clips" / out_name
    vw = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w * S + 280, h * S))
    for k in range(lo, hi + 1):
        r = d.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(frames[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        pan = np.full((h * S, 280, 3), 24, np.uint8)
        def put(t, y, c=(255, 255, 255), sc=0.5):
            cv2.putText(pan, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(pan, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
        put(title, 22, sc=0.4)
        put("0.5x speed", 42, sc=0.4)
        put(f"x {int(r.x)}   frame {int(r.frame)}", 72)
        sd = "-" if pd.isna(r.stim_d) else f"{r.stim_d:.0f} px"
        put(f"stim_src {r.stim_src}", 98)
        put(f"stim_d {sd}", 124)
        put(f"TTMn {r.ttmn:.3f} (thr {thr:.3f})", 150, (0, 255, 255) if r.ttmn >= thr else (255, 255, 255))
        put(f"A {'DOWN' if r.a else 'up'}", 178, (0, 255, 0) if r.a else (200, 200, 200))
        put(f"enemies: {'' if pd.isna(r.enemies) else r.enemies}", 210, sc=0.36)
        ps, ysp, est = r.extra
        put(f"Mario state {ps:02X}{' DYING' if ps == 11 else ''}  vy {ysp:+d}", 236, (0, 120, 255) if ps == 11 else (200, 200, 200), 0.4)
        put(f"enemy states {est}  (st04 = stomped)", 254, sc=0.36)
        if k == hi:
            put("END: " + s["cause"], 296, (0, 0, 255), 0.6)
        vw.write(np.concatenate([img, pan], axis=1))
    vw.release()
    print(dict(max_x=s["max_x"], cause=s["cause"], frames=hi - lo + 1, secs=(hi - lo + 1) / 30, lo=lo))
    print(d.iloc[-12:][["frame", "x", "y", "stim_src", "stim_d", "ttmn", "a", "enemies"]].to_string())


if __name__ == "__main__":
    main(*sys.argv[1:])
