"""Part C1 clips with the one-colour-language overlay (flyrun/SPEC.md): RED = looming (enemy / pipe face / pit tower; pit base thin outline), GREEN = pleasant (line under a humming
block with the hum level; box over the mushroom with smell L / R), WHITE circle = home (right edge of the screen at his eye height; size / opacity ~ HOME_R; hidden when HOME_SENSE is off).
python -m flyrun.c1_clip  -> clips/C1_all_four.mp4 (arm C, noop 0, sigma 0, whole run, 1x) and clips/C1_death_1220.mp4 (arm A passing x 1170-1260, then arm B dying there, 0.5x)"""
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from . import c1_run as C
from .knobs import Knobs

ROOT = Path(__file__).resolve().parent
S, PANEL = 3, 300
RED, GREEN, WHITE = (0, 0, 255), (0, 220, 0), (255, 255, 255)


def draw(img, r, sl, kn, home_on):
    """Overlay on the pre-step frame. r = this frame's row, sl = screen left (world px) at this frame."""
    sx = lambda wx: int((wx - sl) * S)
    sy = lambda ty: int((ty + 32) * S)
    if isinstance(r.box, tuple):
        bx, top, bw, bh = r.box
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 3)
    if isinstance(getattr(r, "base", None), tuple):
        bx, top, bw, bh = r.base
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 1)
    hb = getattr(r, "hum_block", None)
    if isinstance(hb, tuple):
        bx, bottom, _ = hb
        cv2.line(img, (sx(bx), sy(bottom) + 4), (sx(bx + 16), sy(bottom) + 4), GREEN, 4)
        cv2.putText(img, f"hum {r.hum_level:.1f}", (sx(bx), sy(bottom) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 1, cv2.LINE_AA)
    sb = getattr(r, "smell_box", None)
    if isinstance(sb, tuple):
        bx, top, bw, bh = sb
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), GREEN, 3)
        cv2.putText(img, f"smell L {r.smell_L:.0f} R {r.smell_R:.0f}", (sx(bx), sy(top) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, GREEN, 1, cv2.LINE_AA)
    if home_on:
        eye = r.feet_pre - (24 if r.powerup_pre >= 1 else 16)
        cx, cy, rad = img.shape[1] - 18, sy(eye), int(4 + 28 * kn.HOME_R)
        ov = img.copy()
        cv2.circle(ov, (cx, cy), rad, WHITE, -1)
        cv2.addWeighted(ov, min(1.0, kn.HOME_R), img, 1 - min(1.0, kn.HOME_R), 0, img)


def render(parts, path, fps, speed):
    vw = None
    n = 0
    for df, idx, label in parts:
        kn = Knobs()
        fr = df.attrs["frames"]
        h, w = fr[0].shape[:2]
        if vw is None:
            vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w * S + PANEL, h * S))
        tog = df.attrs["toggles"]
        home_on = bool(tog["home"])
        d = df.copy()
        d["feet_pre"] = d["y"].shift(1, fill_value=176)
        d["powerup_pre"] = d["powerup"].shift(1, fill_value=0)
        d["sl_pre"] = d["screen_left"].shift(1, fill_value=0)
        for k in idx:
            r = d.iloc[k]
            img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(fr[k]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
            draw(img, r, float(r.sl_pre), kn, home_on)
            pan = np.full((h * S, PANEL, 3), 24, np.uint8)

            def put(t, y, c=(255, 255, 255), sc=0.45):
                cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
            put("C1: four drives, full 1-1", 20, sc=0.45)
            put(label, 42, (0, 200, 255), 0.4)
            put("on: " + " ".join(k for k, v in tog.items() if v) + "  off: " + " ".join(k for k, v in tog.items() if not v), 64, sc=0.32)
            put(f"{speed}  frame {int(r.frame)}  x {int(r.x)}  score {int(r.score)}", 88, sc=0.42)
            put(f"power {'big' if r.powerup >= 1 else 'small'}   threat {r.threat_kind}", 110, sc=0.42)
            thr = kn.TTMN_THRESH
            put(f"TTMn {r.ttmn:.2f}  (thr {thr:.2f})", 140, (0, 255, 255) if r.ttmn >= thr else WHITE)
            cv2.rectangle(pan, (8, 148), (288, 162), (70, 70, 70), 1)
            cv2.rectangle(pan, (8, 148), (8 + int(min(1.0, r.ttmn) * 280), 162), (0, 200, 255), -1)
            cv2.line(pan, (8 + int(min(1.0, thr) * 280), 144), (8 + int(min(1.0, thr) * 280), 166), WHITE, 1)
            put(f"steer {r.steer:+.4f}   (L < -0.01 < R)", 190, sc=0.4)
            mid = 148
            cv2.rectangle(pan, (8, 198), (288, 214), (70, 70, 70), 1)
            for t in (-0.01, 0.01):
                cv2.line(pan, (int(mid + t / 0.06 * 130), 196), (int(mid + t / 0.06 * 130), 218), (0, 140, 255), 2)
            cv2.circle(pan, (int(np.clip(mid + r.steer / 0.06 * 130, 10, 286)), 206), 5, (0, 255, 255), -1)
            btn = "".join(n_ for n_, on in (("Left ", r.left), ("Right ", r.right), ("A", r.a)) if on) or "none"
            put(f"buttons: {btn}", 244, (0, 255, 0) if btn != "none" else (200, 200, 200))
            hl = getattr(r, "hum_level", 0.0)
            put(f"hum {0.0 if pd.isna(hl) else hl:.1f}", 270, GREEN)
            put("red = looming   green = hum / smell", 700, RED, 0.38)
            put("white circle = home", 720, WHITE, 0.38)
            vw.write(np.concatenate([img, pan], axis=1))
            n += 1
    vw.release()
    print(Path(path).name, n, "frames = %.1f s at %s" % (n / fps, speed))


def main():
    ep0 = dict(noop_start=0, seed=0, sigma=0.0)
    s, dfc = C.episode("C", ep0, record=True)
    print("arm C noop 0 sigma 0:", {k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "score")})
    render([(dfc, list(range(len(dfc))), "arm C: looming+home+hum+smell, noop 0, sigma 0")], ROOT / "clips" / "C1_all_four.mp4", 60, "1x")
    ep3 = dict(noop_start=3, seed=101, sigma=0.0)
    import json
    from . import episodes4
    e = [x for x in episodes4.HOLDOUT if x["noop_start"] == 3 and x["sigma"] == 0.0][0]
    ep3 = dict(noop_start=3, seed=e["seed"], sigma=0.0)
    sa, dfa = C.episode("A", ep3, record=True)
    sb, dfb = C.episode("B", ep3, record=True)
    win = lambda df, lo, hi: [i for i in range(len(df)) if lo <= df.x.iloc[i] <= hi and i > 600]
    ia = win(dfa, 1150, 1262)
    ib = list(range(max(0, len(dfb) - 110), len(dfb)))
    render([(dfa, ia, "A (no hum): passes the Goomba on the bricks"), (dfb, ib, "B (+hum): jumps at the block, dies")], ROOT / "clips" / "C1_death_1220.mp4", 30, "0.5x")


if __name__ == "__main__":
    main()
