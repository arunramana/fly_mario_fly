"""Stitch an arm's evolution into one mp4: generation 0, then each generation where the best
max_x jumped, each replayed exactly and labelled "gen N | max_x | death cause".
CLI: python -m flyrun.montage --arm fly [--restart K]"""
import argparse
import json

import cv2
import numpy as np
import pandas as pd

from .render_stage import EVO, best_restart, replay

SCALE = 2


def label(frame, text):
    f = cv2.resize(np.ascontiguousarray(frame), None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_NEAREST)
    cv2.rectangle(f, (0, 0), (f.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(f, text, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return f


def stages(arm, restart):
    g = pd.read_csv(EVO / arm / "gen.csv")
    g = g[g.restart == restart].sort_values("gen")
    keep, prev = [], -1
    for _, row in g.iterrows():
        if row.gen == 0 or row.best_max_x > prev:
            keep.append(row)
        prev = max(prev, row.best_max_x)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["fly", "theta"])
    ap.add_argument("--restart", type=int, default=None)
    a = ap.parse_args()
    r = best_restart(a.arm) if a.restart is None else a.restart
    out = EVO / a.arm / "montage.mp4"
    writer = None
    for row in stages(a.arm, r):
        u = np.array(json.loads(row.gen_best_u))
        s, df = replay(a.arm, u)
        text = f"gen {int(row.gen)} | max_x {s['max_x']} | {s['cause']}"
        print(text)
        for fr in df.attrs["frames"]:
            lab = label(fr, text)
            if writer is None:
                h, w = lab.shape[:2]
                writer = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))
            writer.write(cv2.cvtColor(lab, cv2.COLOR_RGB2BGR))
        for _ in range(20):   # short hold on the last frame between stages
            writer.write(cv2.cvtColor(lab, cv2.COLOR_RGB2BGR))
    writer.release()
    print("->", out)


if __name__ == "__main__":
    main()
