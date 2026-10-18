"""Part C1: all four drives together on the full 1-1 HOLDOUT (10 episodes per arm, enemies ON), 881-neuron brain, frozen gains.
Arms: A = looming + home; B = + hum; C = + hum + smell.  Section 2 (regression) is arm A against the saved S3e traces.
python -m flyrun.c1_run            -> runs/C1_<arm>_<noop>_<sigma>.csv, runs/C1_arms.json   (python -m flyrun.c1_run A  = arm A only, regression)
python -m flyrun.c1_clip           -> clips/C1_all_four.mp4 (see c1_clip.py)"""
import hashlib
import json
import multiprocessing as mp
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import episodes4
from . import level
from .knobs import Knobs, toggle_set

ROOT = Path(__file__).resolve().parent
WFILE, BODIES = "W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet"
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2")
ARMS = dict(A=dict(HUM_SENSE=False, SMELL_SENSE=False), B=dict(HUM_SENSE=True, SMELL_SENSE=False), C=dict(HUM_SENSE=True, SMELL_SENSE=True))
QB = pd.read_csv(ROOT / "runs" / "O0_qblocks.csv")[["x", "row"]].itertuples(index=False, name=None)
QBLOCKS = [(int(x), int(r)) for x, r in QB]
_BRAIN = {}


class Probe:
    """Reads RAM only: power-up state, coin counter, the mushroom, and which '?' blocks have been hit (tile 192/193 -> 35/196 while on screen)."""

    def __init__(self):
        self.seen, self.hits, self.f = set(), [], 0

    def __call__(self, ram):
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        mx = int(ram[0x006D]) * 256 + int(ram[0x0086])
        for bx, row in QBLOCKS:
            if not (left - 16 <= bx < left + 256):
                continue
            t = level.tile(ram, bx, row)
            if t in (192, 193):
                self.seen.add((bx, row))
            elif t in (35, 196) and (bx, row) in self.seen:
                self.seen.discard((bx, row))
                self.hits.append(dict(block_x=bx, row=row, frame=self.f, mario_x=mx))
        on = int(ram[0x0F + 5]) and int(ram[0x16 + 5]) == 0x2E
        out = dict(screen_left=left, powerup=int(ram[0x0756]), coins=int(ram[0x075E]), mush_x=(int(ram[0x6E + 5]) * 256 + int(ram[0x87 + 5])) if on else np.nan,
                   blocks_hit=len(self.hits))
        self.f += 1
        return out


def _brain():
    if "b" not in _BRAIN:
        os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = WFILE, BODIES
        from .brain import load_brain
        _BRAIN["b"] = load_brain()
    return _BRAIN["b"]


def episode(arm, ep, record=False, enemy_input=True, max_frames=3000):
    from .run import run_episode
    k = replace(KN, SENSOR_NOISE=ep["sigma"], **ARMS[arm])
    pr = Probe()
    s, df = run_episode(k, _brain(), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, record=record, probe=pr, max_frames=max_frames, enemy_input=enemy_input)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, toggle_set(k, enemy_input=enemy_input)
    return s, df


def trace_cols(df):
    """S3e columns + hum, smell, steer, toggle set, score, power state."""
    box = lambda b: "" if not isinstance(b, tuple) else " ".join(str(int(v)) for v in b)
    out = df[["frame", "x", "y", "air"]].copy().rename(columns={"y": "feet_y", "air": "airborne"})
    out["threat"] = df.threat_kind
    out["box_x_top_w_h"] = df.box.map(box)
    out["pit_base_x_top_w_h"] = df.base.map(box)
    out["theta_deg"] = np.degrees(df.theta).round(2)
    out["ttmn"] = df.ttmn.round(4)
    out["steer"] = df.steer.round(5)
    out["a"], out["right"], out["left"] = df.a, df.right, df.left
    out["hum_level"] = df.get("hum_level", pd.Series(0.0, index=df.index)).fillna(0).round(4)
    out["hum_block_x"] = df.get("hum_block", pd.Series([None] * len(df))).map(lambda b: b[0] if isinstance(b, tuple) else np.nan)
    out["smell_L"] = df.get("smell_L", pd.Series(0.0, index=df.index)).fillna(0).round(3)
    out["smell_R"] = df.get("smell_R", pd.Series(0.0, index=df.index)).fillna(0).round(3)
    out["mushroom_x"] = df.mush_x
    out["powerup"], out["coins"], out["blocks_hit"], out["score"] = df.powerup, df.coins, df.blocks_hit, df.score
    out["toggles"] = json.dumps(df.attrs["toggles"], separators=(",", ":"))
    return out


def analyse(s, df, ep):
    onsets = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0) & (df.air == 0)]
    hum = df.get("hum_level", pd.Series(0.0, index=df.index)).fillna(0)
    smL, smR = df.get("smell_L", pd.Series(0.0, index=df.index)).fillna(0), df.get("smell_R", pd.Series(0.0, index=df.index)).fillna(0)
    loom_on = df.threat_kind != "none"
    quiet = (~loom_on) & (hum == 0) & (smL == 0) & (smR == 0)          # nothing in view at all
    mush = df.mush_x.notna()
    lprev = df.left.shift(1, fill_value=0)
    lon = (df.left == 1) & (lprev == 0)
    ov = [dict(frame=int(r.frame), x=int(r.x), kind=str(r.threat_kind), theta_deg=float(np.degrees(r.theta)), d=None if pd.isna(r.stim_d) else float(r.stim_d), hum_level=float(hum[r.Index]))
          for r in onsets.itertuples() if hum[r.Index] > 0 and r.threat_kind != "none"]
    eaten_f = None
    p = df.powerup.to_numpy()
    for i in range(1, len(p)):
        if p[i] > p[i - 1]:
            eaten_f = int(df.frame.iloc[i]); break
    shrink = int(((df.powerup.diff() < 0)).sum())
    h = hashlib.md5((",".join(map(str, df.x)) + "|" + ",".join(map(str, df.a))).encode()).hexdigest()[:10]
    hits = df.attrs["hits"]
    return dict(noop_start=ep["noop_start"], seed=ep["seed"], sigma=ep["sigma"], flag=bool(s["flag_get"]), max_x=s["max_x"], end=s["end_reason"], x_end=s["x_at_end"], cause=s["cause"],
                frames=s["frames"], traj=h, score=s["score"], blocks_hit=[b["block_x"] for b in hits], blocks_hit_detail=hits, n_blocks=len(hits),
                coins=int(df.coins.iloc[-1] - df.coins.iloc[0]), mushroom_out=bool(mush.any()), mushroom_eaten=eaten_f is not None, eaten_frame=eaten_f,
                big_at_end=bool(df.powerup.iloc[-1] >= 1), shrinks=shrink,
                overlap_onsets=ov, n_onsets=int(len(onsets)),
                left_frames=int(df.left.sum()), left_presses=int(lon.sum()), left_frames_mush_in_view=int(((df.left == 1) & mush).sum()), left_presses_mush_in_view=int((lon & mush).sum()),
                left_frames_mush_not_in_view=int(((df.left == 1) & ~mush).sum()), left_presses_mush_not_in_view=int((lon & ~mush).sum()),
                a_onsets_no_stimulus=int(quiet[onsets.index].sum()), a_frames_no_stimulus=int(((df.a == 1) & quiet).sum()), frames_mush_in_view=int(mush.sum()),
                onsets=[(float(np.degrees(r.theta)), str(r.threat_kind), None if pd.isna(r.stim_d) else float(r.stim_d), int(r.x)) for r in onsets.itertuples()])


def _job(job):
    arm, ep = job
    s, df = episode(arm, ep)
    trace_cols(df).to_csv(ROOT / "runs" / f"C1_{arm}_{ep['noop_start']}_{ep['sigma']}.csv", index=False, lineterminator="\n")
    r = analyse(s, df, ep)
    r["arm"] = arm
    r["toggles"] = df.attrs["toggles"]
    return r


def main():
    arms = sys.argv[1:] or list(ARMS)
    eps = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
    with mp.get_context("spawn").Pool(6) as pool:
        res = pool.map(_job, [(a, e) for a in arms for e in eps])
    path = ROOT / "runs" / "C1_arms.json"
    out = json.load(open(path)) if path.exists() else {}
    for a in arms:
        out[a] = [r for r in res if r["arm"] == a]
        ep = out[a]
        print(a, "flags", sum(r["flag"] for r in ep), "max_x", [r["max_x"] for r in ep], "causes", [r["cause"] for r in ep], flush=True)
    json.dump(out, open(path, "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
