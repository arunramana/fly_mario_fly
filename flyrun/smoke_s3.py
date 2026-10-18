"""Part S3: the default-knob smoke run with the S3 senses (rim tiles + pit hole), noop 0, sigma 0, unassisted.
python -m flyrun.smoke_s3   -> runs/S3e_smoke_log.csv, runs/S3e_jumps.csv, runs/S3e_full_run.csv, pit take-off table, clips/S3e_full_run.mp4 (1x)"""
import numpy as np

from . import level
from .smoke_s2 import ROOT, run, window, write_clip


def pit_table(df, jt):
    """For each pit: how many fly jumps took off within 100 px before it up to its far edge, and the take-off distance (front edge -> near edge)."""
    rows = []
    for px, pw in ((1104, 32), (1376, 48), (2448, 32)):
        js = jt[(jt.x_takeoff + 12 <= px + pw) & (jt.x_takeoff >= px - 100)]
        rows.append(dict(pit=px, width=pw, jumps=len(js), takeoff_dist=[int(px - (x + 12)) for x in js.x_takeoff],
                         landing_x=[int(x) for x in js.x_landing]))
    return rows


def save_trace(df, path):
    """Per-frame trace: frame, x, feet y, airborne, chosen threat (type, box [x top w h], pit base box), theta (deg), TTMn, A, Right, Left."""
    box = lambda b: "" if not isinstance(b, tuple) else " ".join(str(int(v)) for v in b)
    out = df[["frame", "x", "y", "air"]].copy()
    out["threat"] = df.threat_kind
    out["box_x_top_w_h"] = df.box.map(box)
    out["pit_base_x_top_w_h"] = df.base.map(box)
    out["theta_deg"] = np.degrees(df.theta).round(2)
    out["ttmn"] = df.ttmn.round(4)
    out["a"], out["right"], out["left"] = df.a, df.right, df.left
    out = out.rename(columns={"y": "feet_y", "air": "airborne"})
    out.to_csv(path, index=False, lineterminator="\n")


def main():
    s, df = run("S3e")
    import pandas as pd
    jt = pd.read_csv(ROOT / "runs" / "S3e_jumps.csv")
    for r in pit_table(df, jt):
        print(r)
    save_trace(df, ROOT / "runs" / "S3e_full_run.csv")
    write_clip([(df, list(range(len(df))), "")], ROOT / "clips" / "S3e_full_run.mp4", "S3e: cleared enemy hands over", fps=60, speed="1x")



def pair_clip():
    """The Goomba pair near x 1769-1810 on HOLDOUT noop 11, sigma 0 (died there in S3d), 0.5x, <= 10 s."""
    from dataclasses import replace
    from . import episodes4
    from .brain import load_brain
    from .diagnose7b import capture
    from .smoke_s2 import KN, extra
    e = episodes4.HOLDOUT[1]
    assert (e["noop_start"], e["sigma"]) == (11, 0.0)
    s, df = capture(replace(KN, SENSOR_NOISE=e["sigma"]), dict(noop_start=e["noop_start"], seed=e["seed"]), load_brain(), record=True, extra=extra)
    print("pair clip episode", e, {k: s[k] for k in ("max_x", "end_reason", "cause")})
    idx = window(df, 1745, 1830, pre=20, post=10)[:290]
    write_clip([(df, idx, "")], ROOT / "clips" / "S3e_pair.mp4", "S3e: Goomba pair (HOLDOUT noop 11, sigma 0)")


if __name__ == "__main__":
    import sys
    pair_clip() if sys.argv[1:] == ["pair"] else main()
