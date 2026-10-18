"""Part S1 smoke run: default knobs, SENSES_VERSION v2, 1-1 from the start. Logs the chosen threat per frame and renders
clips/S1_senses_v2.mp4 (<= 20 s, start through pipe 1) with a box on the chosen threat and theta / d on screen.
A look at the new eye, not a score."""
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from .brain import load_brain
from .knobs import Knobs
from .diagnose7b import capture

ROOT = Path(__file__).resolve().parent
S = 3                          # clip scale
SCROLL_ADDR = (0x071A, 0x071C)  # screen-left world x: page, x


def main():
    kn = replace(Knobs(), SENSES_VERSION="v2", SENSOR_NOISE=0.0)
    scroll = lambda ram: int(ram[0x071A]) * 256 + int(ram[0x071C])   # world x of the screen's left edge, after the step
    s, df = capture(kn, dict(noop_start=0, seed=0), load_brain(), record=True, extra=scroll)
    print({k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "a_frac", "blind_presses")})
    out = ROOT / "runs" / "S1_smoke_log.csv"
    cols = ["frame", "x", "air", "threat_kind", "threat_id", "stim_d", "theta", "dtheta", "ttmn", "a"]
    df[cols].to_csv(out, index=False, lineterminator="\n")
    # frames from the start until Mario has passed pipe 1 (x 448+32) + a short tail, capped at 20 s of 0.5x playback
    frames = df.attrs["frames"]
    end = int(df[df.x >= 500].frame.iloc[0]) if (df.x >= 500).any() else len(df) - 1
    end = min(end + 20, len(df) - 1, 1200)
    scr = list(df.extra)
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(ROOT / "clips" / "S1_senses_v2.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w * S, h * S))
    for k in range(0, end + 1):
        r = df.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(frames[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        if isinstance(r.box, tuple):
            bx, top, bw, bh = r.box
            sx = bx - scr[k]
            y0 = top + 32          # tile-buffer y -> screen y (32 px HUD offset: ground row 11 = y 176 -> 208)
            col = {"goomba": (0, 0, 255), "koopa": (0, 165, 255), "shell": (0, 165, 255), "face": (255, 200, 0), "pit": (255, 0, 255)}.get(r.threat_kind, (255, 255, 255))
            cv2.rectangle(img, (int(sx * S), int(y0 * S)), (int((sx + bw) * S), int((y0 + bh) * S)), col, 2)
        txt = f"x {int(r.x)}  threat {r.threat_kind} {r.threat_id}"
        txt2 = f"d {r.stim_d:.0f}px  theta {np.degrees(r.theta):.0f}deg  dtheta {np.degrees(r.dtheta):.1f}  TTMn {r.ttmn:.2f}  A {'DOWN' if r.a else 'up'}" if not np.isnan(r.stim_d) else "no threat"
        for i, t in enumerate((txt, txt2)):
            cv2.putText(img, t, (6, 16 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, t, (6, 16 + 16 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        vw.write(img)
    vw.release()
    print("clip frames", end + 1, "secs at 30fps (=0.5x)", (end + 1) / 30)


if __name__ == "__main__":
    main()
