"""Part S2 smoke run: default knobs, senses v2 + motor v2, sigma 0, 1-1 from the start. No pass/fail.
Writes runs/S2_smoke_log.csv (per frame), runs/S2_jumps.csv (per jump), prints the death map, renders clips/S2_fly_held_jump.mp4."""
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from . import env as E
from .brain import load_brain
from .diagnose7b import capture
from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
S = 3


def extra(ram):
    states = tuple(int(ram[0x1E + s]) for s in range(E.N_ENEMY_SLOTS) if int(ram[E.ADDR_ENEMY_ACTIVE + s]) and int(ram[E.ADDR_ENEMY_TYPE + s]) != E.POWERUP_ID)
    return (int(ram[0x071A]) * 256 + int(ram[0x071C]), states, int(ram[0x001D]))


def jumps(df, s):
    """One row per jump: from an A onset while grounded to the landing frame (airborne -> grounded) or the end of the episode."""
    rows, k, n = [], 0, len(df)
    air = df["air"].to_numpy()
    a = df["a"].to_numpy()
    while k < n:
        if a[k] == 1 and (k == 0 or a[k - 1] == 0) and air[k] == 0:
            t0 = k
            land = next((j for j in range(t0 + 1, n) if air[j - 1] == 1 and air[j] == 0), None)
            end = land if land is not None else n - 1
            seg = df.iloc[t0:end + 1]
            held = int(seg.a.sum())
            whys = [w for w in seg.a_why if isinstance(w, str) and w]
            reason = whys[0] if whys else ("died / ended in the air" if land is None else "still down at landing")
            stomped = any(any(st == 4 for st in e[1]) for e in df.iloc[t0:min(end + 3, n)].extra) and \
                not any(any(st == 4 for st in e[1]) for e in df.iloc[max(0, t0 - 1):t0].extra)
            thr = df.iloc[t0]
            bx, bw = (thr.box[0], thr.box[2]) if isinstance(thr.box, tuple) else (None, None)
            xl = int(df.iloc[end].x)
            if land is None:
                outcome = "died" if s["end_reason"] == "died" else s["end_reason"]
            elif stomped:
                outcome = "landed on enemy (stomped)"
            elif thr.threat_kind == "face":
                outcome = "landed on/past the face" if xl + 12 > bx else "short of the face"
            elif thr.threat_kind == "goomba" or thr.threat_kind == "koopa":
                outcome = "no contact (not stomped, survived)" if not (s["end_reason"] == "died" and end >= n - 30) else "died soon after"
            else:
                outcome = "survived the pit tile" if s["end_reason"] != "died" or end < n - 30 else "died soon after"
            rows.append(dict(frame=t0, x_takeoff=int(thr.x), threat=f"{thr.threat_kind} {thr.threat_id}", takeoff_d=thr.stim_d, theta_deg=np.degrees(thr.theta),
                             frames_held=held, release_reason=reason, landing_frame=land, x_landing=int(df.iloc[end].x), outcome=outcome))
            k = end + 1
        else:
            k += 1
    return pd.DataFrame(rows)


def main():
    kn = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0)
    s, df = capture(kn, dict(noop_start=0, seed=0), load_brain(), record=True, extra=extra)
    print({k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "a_frac", "blind_presses", "left_presses", "left_frames")}, s.get("LEFT_PRESS_WARNING", ""))
    cols = ["frame", "x", "y", "air", "threat_kind", "threat_id", "stim_d", "theta", "dtheta", "ttmn", "a", "a_why", "left"]
    df[cols].to_csv(ROOT / "runs" / "S2_smoke_log.csv", index=False, lineterminator="\n")
    jt = jumps(df, s)
    jt.to_csv(ROOT / "runs" / "S2_jumps.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 250)
    print(jt.head(12).to_string())
    print("jumps", len(jt), "outcomes", jt.outcome.value_counts().to_dict(), "release reasons", jt.release_reason.value_counts().to_dict())
    tail = df.iloc[-25:]
    print(tail[["frame", "x", "y", "air", "threat_kind", "stim_d", "ttmn", "a", "a_why"]].to_string())
    # clip: from the start through the third obstacle (pipe 2 passed or 1200 frames), 0.5x
    frames = df.attrs["frames"]
    objs = (df.threat_id.fillna("") != df.threat_id.fillna("").shift()) & (df.threat_kind.isin(["goomba", "face"]))
    ends = df.index[(df.x >= 640)]
    end = int(min(ends[0] + 30 if len(ends) else len(df) - 1, 1199, len(df) - 1))
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(ROOT / "clips" / "S2_fly_held_jump.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w * S + 260, h * S))
    thr = kn.TTMN_THRESH
    for k in range(end + 1):
        r = df.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(frames[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        if isinstance(r.box, tuple):
            bx, top, bw, bh = r.box
            sx, y0 = bx - r.extra[0], top + 32
            col = {"goomba": (0, 0, 255), "koopa": (0, 165, 255), "shell": (0, 165, 255), "face": (255, 200, 0), "pit": (255, 0, 255)}.get(r.threat_kind, (255, 255, 255))
            cv2.rectangle(img, (int(sx * S), int(y0 * S)), (int((sx + bw) * S), int((y0 + bh) * S)), col, 2)
        pan = np.full((h * S, 260, 3), 24, np.uint8)

        def put(t, y, c=(255, 255, 255), sc=0.5):
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
        put("S2: senses v2 + fly-held jump", 20, sc=0.42)
        put(f"0.5x  frame {int(r.frame)}  x {int(r.x)}", 44, sc=0.42)
        put(f"threat {r.threat_kind} {r.threat_id}", 70, sc=0.42)
        sd = "-" if pd.isna(r.stim_d) else f"{r.stim_d:.0f} px"
        put(f"d {sd}  theta {np.degrees(r.theta):.0f} deg", 92, sc=0.42)
        put(f"TTMn {r.ttmn:.2f}  (thr {thr:.2f})", 120, (0, 255, 255) if r.ttmn >= thr else (255, 255, 255))
        cv2.rectangle(pan, (8, 128), (248, 142), (70, 70, 70), 1)
        cv2.rectangle(pan, (8, 128), (8 + int(min(1.0, r.ttmn / 1.0) * 240), 142), (0, 200, 255), -1)
        cv2.line(pan, (8 + int(min(1.0, thr) * 240),) * 1 + (124,), (8 + int(min(1.0, thr) * 240), 146), (255, 255, 255), 1)
        put(f"A {'DOWN' if r.a else 'up'}", 176, (0, 255, 0) if r.a else (200, 200, 200))
        put(f"airborne {'YES' if r.air else 'no'}", 202, (0, 200, 255) if r.air else (200, 200, 200))
        if isinstance(r.a_why, str) and r.a_why:
            put("released: " + r.a_why.replace("_", " "), 228, (0, 120, 255), 0.45)
        vw.write(np.concatenate([img, pan], axis=1))
    vw.release()
    print("clip frames", end + 1, "= %.1f s at 0.5x" % ((end + 1) / 30))


if __name__ == "__main__":
    main()
