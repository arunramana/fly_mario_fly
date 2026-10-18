"""Part S2 / S2b smoke runs: default knobs, senses v2 + motor v2, sigma 0, 1-1. No pass/fail.
Writes runs/<tag>_smoke_log.csv (per frame), runs/<tag>_jumps.csv (per jump), prints the jump table and the end of the run,
renders a clip (0.5x, with TTMn / A / airborne overlay and the S1 threat box).
python -m flyrun.smoke_s2          -> S2 (first three obstacles)
python -m flyrun.smoke_s2 S2b      -> S2b: from the start, plus an ASSISTED run (scripted driver to x 1000, then the fly) for pit 1
python -m flyrun.smoke_s2 S2c      -> S2c: same runs with the S2c senses (above-and-over faces, pit virtual wall; superseded by S3 senses); clip clips/S2c.mp4"""
import sys
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
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0)


def extra(ram):
    states = tuple(int(ram[0x1E + s]) for s in range(E.N_ENEMY_SLOTS) if int(ram[E.ADDR_ENEMY_ACTIVE + s]) and int(ram[E.ADDR_ENEMY_TYPE + s]) != E.POWERUP_ID)
    return (int(ram[0x071A]) * 256 + int(ram[0x071C]), states, int(ram[0x001D]))


def jumps(df, s):
    """One row per FLY jump: from an A onset while grounded to the landing frame (airborne -> grounded) or the end of the episode."""
    rows, k, n = [], 0, len(df)
    air, a, fly = df["air"].to_numpy(), df["a"].to_numpy(), (df["driver"] == "fly").to_numpy()
    while k < n:
        if fly[k] and a[k] == 1 and (k == 0 or a[k - 1] == 0) and air[k] == 0:
            t0 = k
            land = next((j for j in range(t0 + 1, n) if air[j - 1] == 1 and air[j] == 0), None)
            end = land if land is not None else n - 1
            seg = df.iloc[t0:end + 1]
            whys = [w for w in seg.a_why if isinstance(w, str) and w]
            reason = whys[0] if whys else ("died / ended in the air" if land is None else "still down at landing")
            stomped = any(any(st == 4 for st in e[1]) for e in df.iloc[t0:min(end + 3, n)].extra) and \
                not any(any(st == 4 for st in e[1]) for e in df.iloc[max(0, t0 - 1):t0].extra)
            thr = df.iloc[t0]
            bx = thr.box[0] if isinstance(thr.box, tuple) else None
            xl = int(df.iloc[end].x)
            died_soon = s["end_reason"] == "died" and end >= n - 30
            if land is None:
                outcome = "died" if s["end_reason"] == "died" else s["end_reason"]
            elif stomped:
                outcome = "landed on enemy (stomped)"
            elif thr.threat_kind == "face":
                outcome = "landed on/past the face" if xl + 12 > bx else "short of the face"
            elif thr.threat_kind in ("goomba", "koopa"):
                outcome = "died soon after" if died_soon else "no contact (not stomped, survived)"
            else:
                outcome = "died soon after" if died_soon else "survived the pit threat"
            rows.append(dict(frame=t0, x_takeoff=int(thr.x), threat=f"{thr.threat_kind} {thr.threat_id}", takeoff_d=thr.stim_d, theta_deg=np.degrees(thr.theta),
                             frames_held=int(seg.a.sum()), release_reason=reason, landing_frame=land, x_landing=xl, outcome=outcome))
            k = end + 1
        else:
            k += 1
    return pd.DataFrame(rows)


def window(df, lo, hi, pre=40, post=30):
    i0 = int(df.index[df.x >= lo][0]) - pre
    ih = df.index[df.x >= hi]
    return list(range(max(i0, 0), min((int(ih[0]) if len(ih) else len(df) - 1) + post, len(df) - 1) + 1))


def run(tag, **run_kw):
    s, df = capture(KN, dict(noop_start=0, seed=0), load_brain(), record=True, extra=extra, **run_kw)
    print(tag, {k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "a_frac", "blind_presses", "left_presses", "left_frames")}, s.get("LEFT_PRESS_WARNING", ""))
    cols = ["frame", "x", "y", "air", "driver", "threat_kind", "threat_id", "stim_d", "theta", "dtheta", "ttmn", "a", "a_why", "left"]
    df[cols].to_csv(ROOT / "runs" / f"{tag}_smoke_log.csv", index=False, lineterminator="\n")
    jt = jumps(df, s)
    jt.to_csv(ROOT / "runs" / f"{tag}_jumps.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 250)
    print(jt.to_string())
    print("jumps", len(jt), "outcomes", jt.outcome.value_counts().to_dict(), "release reasons", jt.release_reason.value_counts().to_dict())
    print(df.iloc[-6:][["frame", "x", "y", "air", "threat_kind", "stim_d", "ttmn", "a", "a_why"]].to_string())
    return s, df


def write_clip(parts, path, title, fps=30, speed="0.5x"):
    """parts: [(df, idx, label)]; 0.5x playback (30 fps of the 60 Hz game)."""
    thr = KN.TTMN_THRESH
    vw, n = None, 0
    for df, idx, label in parts:
        frames = df.attrs["frames"]
        h, w = frames[0].shape[:2]
        if vw is None:
            vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w * S + 260, h * S))
        for k in idx:
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
            put(title, 20, sc=0.42)
            put(label, 40, (0, 200, 255) if "ASSISTED" in label else (200, 200, 200), 0.4)
            put(f"{speed}  frame {int(r.frame)}  x {int(r.x)}", 62, sc=0.42)
            put(f"threat {r.threat_kind} {r.threat_id}", 86, sc=0.42)
            sd = "-" if pd.isna(r.stim_d) else f"{r.stim_d:.0f} px"
            put(f"d {sd}  theta {np.degrees(r.theta):.0f} deg", 108, sc=0.42)
            put(f"TTMn {r.ttmn:.2f}  (thr {thr:.2f})", 134, (0, 255, 255) if r.ttmn >= thr else (255, 255, 255))
            cv2.rectangle(pan, (8, 142), (248, 156), (70, 70, 70), 1)
            cv2.rectangle(pan, (8, 142), (8 + int(min(1.0, r.ttmn) * 240), 156), (0, 200, 255), -1)
            cv2.line(pan, (8 + int(min(1.0, thr) * 240), 138), (8 + int(min(1.0, thr) * 240), 160), (255, 255, 255), 1)
            put(f"A {'DOWN' if r.a else 'up'}", 190, (0, 255, 0) if r.a else (200, 200, 200))
            put(f"airborne {'YES' if r.air else 'no'}", 216, (0, 200, 255) if r.air else (200, 200, 200))
            if isinstance(r.a_why, str) and r.a_why:
                put("released: " + r.a_why.replace("_", " "), 242, (0, 120, 255), 0.45)
            vw.write(np.concatenate([img, pan], axis=1))
            n += 1
    vw.release()
    print("clip frames", n, "= %.1f s at %s" % (n / fps, speed))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "S2c":
        s, df = run("S2c")                                       # unassisted: he reaches and crosses pit 1 on his own, no assisted run needed
        write_clip([(df, window(df, 840, 960), "unassisted: pipe 4"), (df, window(df, 1008, 1175, pre=10, post=0), "unassisted: pit 1")],
                   ROOT / "clips" / "S2c.mp4", "S2c: above-and-over + pit wall")
    elif len(sys.argv) > 1 and sys.argv[1] == "S2b":
        s, df = run("S2b")
        s2, df2 = run("S2b_pit_assisted", takeover_x=1000)
        fly2 = df2.index[df2.driver == "fly"]
        parts = [(df, window(df, 380, 470), "unassisted run"),
                 (df2, window(df2, int(df2.loc[fly2[0], "x"]) + 20, 1170, pre=60), "ASSISTED: scripted to x 1000, then the fly")]
        write_clip(parts, ROOT / "clips" / "S2b_fixes.mp4", "S2b: face rule + pit-below")
    else:
        s, df = run("S2")
        ends = df.index[df.x >= 640]
        write_clip([(df, list(range(int(min(ends[0] + 30 if len(ends) else len(df) - 1, 1199, len(df) - 1)) + 1)), "")], ROOT / "clips" / "S2_fly_held_jump.mp4", "S2: senses v2 + fly-held jump")


if __name__ == "__main__":
    main()
