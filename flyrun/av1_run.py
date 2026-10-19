"""Part AV1 runner: the E1 evolved genome (runs/E1_progress.json best) on 1-1 HOLDOUT or on 1-2, with the AV1 toggles.
python -m flyrun.av1_run holdout TAG WFILE SOUR HEADROOM [GAIN]   -> runs/AV1_<TAG>_holdout.json (10 episodes, 1-1)
python -m flyrun.av1_run level12 TAG WFILE SOUR HEADROOM [GAIN]   -> runs/AV1_<TAG>_12.json + runs/AV1_<TAG>_12_trace.csv (1-2, noop 0, sigma 0)
WFILE = W_steer_jo_orn.npy (881, the old brain) or W_steer_jo_orn_sour.npy (907); SOUR / HEADROOM = 0 / 1."""
import json
import multiprocessing as mp
import os
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
E1_VALUES = json.load(open(ROOT / "runs" / "E1_progress.json"))["best"]["values"]
BODIES = {"W_steer_jo_orn.npy": "steer_jo_orn_bodies.parquet", "W_steer_jo_orn_sour.npy": "steer_jo_orn_sour_bodies.parquet"}
_B = {}


class ReplayDriver:
    """ASSISTED / DIAGNOSTIC: replays the buttons of the L2 baseline (arm A, noop 0, sigma 0; runs/L2_A_0_0.0.csv), which reaches the x ~ 890 Koopa, until the takeover x; the E1 fly then takes over from a silent
    brain. The emulator is deterministic, so the replay reproduces the arm A state (the scripted player of scripted.py cannot get through the 1-2 opening)."""

    def __init__(self):
        d = pd.read_csv(ROOT / "runs" / "L2_A_0_0.0.csv")
        from . import env as E
        self.acts = [E.LEFT_A if (l and a) else E.LEFT if l else E.RIGHT_A if a else E.RIGHT for l, a in zip(d.left, d.a)]
        self.i = 0

    def act(self, ram):
        a = self.acts[min(self.i, len(self.acts) - 1)]
        self.i += 1
        return a


def frozen_gain():
    p = ROOT / "runs" / "AV1_sour_gain.json"
    return json.load(open(p))["SOUR_GAIN"] if p.exists() else 0.0


def knobs_for(sour, headroom, gain=None, sigma=0.0):
    from . import e1_genome as G
    k, enemy_input = G.knobs_for(E1_VALUES)
    k = replace(k, SENSOR_NOISE=sigma, SOUR_SENSE=bool(sour), HEADROOM_LOOM=bool(headroom), SOUR_GAIN=(frozen_gain() if gain is None else gain) if sour else 0.0)
    return k, enemy_input


def brain(wfile):
    if wfile not in _B:
        os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, BODIES[wfile]
        from .brain import load_brain
        _B[wfile] = load_brain()
    return _B[wfile]


class Probe12:
    """Reads RAM only: '?' blocks found from the tile buffer (tile 192 / 193 -> 35 / 196), power-up state, mushroom, coins. Works on any level."""

    def __init__(self):
        self.seen, self.hits, self.f = set(), [], 0

    def __call__(self, ram):
        from . import level
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        mx = int(ram[0x006D]) * 256 + int(ram[0x0086])
        for wx in range((left // 16) * 16, left + 256, 16):
            for row in range(13):
                t = level.tile(ram, wx, row)
                if t in (192, 193):
                    self.seen.add((wx, row))
                elif t in (35, 196) and (wx, row) in self.seen:
                    self.seen.discard((wx, row))
                    self.hits.append(dict(block_x=wx, row=row, frame=self.f, mario_x=mx))
        on = int(ram[0x0F + 5]) and int(ram[0x16 + 5]) == 0x2E
        out = dict(screen_left=left, powerup=int(ram[0x0756]), coins=int(ram[0x075E]), mush_x=(int(ram[0x6E + 5]) * 256 + int(ram[0x87 + 5])) if on else np.nan, blocks_hit=len(self.hits),
                   lives=int(ram[0x075A]), enemy_slots=" ".join(f"{int(ram[0x16 + s]):02x}:{int(ram[0x1E + s]):02x}:{int(ram[0x6E + s]) * 256 + int(ram[0x87 + s])}" for s in range(5) if int(ram[0x0F + s])))
        self.f += 1
        return out


def episode(wfile, sour, headroom, ep, gain=None, record=False, max_frames=3000, probe=None, takeover_x=None):
    from . import c1_run as C
    from .run import run_episode
    k, enemy_input = knobs_for(sour, headroom, gain, ep["sigma"])
    pr = probe or (C.Probe() if os.environ.get("FLYRUN_LEVEL", "1-1") == "1-1" else Probe12())
    s, df = run_episode(k, brain(wfile), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, enemy_input=enemy_input, record=record, max_frames=max_frames, takeover_x=takeover_x)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, enemy_input)
    return s, df, k


def summarise(s, df, ep):
    from . import c1_run as C
    r = C.analyse(s, df, ep)
    left_on = (df.left == 1) & (df.left.shift(1, fill_value=0) == 0)
    r["backup_frames"] = int(df.backup.sum()) if "backup" in df else 0
    r["backup_presses"] = int(((df.backup == 1) & (df.backup.shift(1, fill_value=0) == 0)).sum()) if "backup" in df else 0
    if "headroom_factor" in df:
        r["headroom_suppressed_frames"] = int((df.headroom_factor.fillna(1) < 1).sum())
    return r


def _job(job):
    wfile, sour, headroom, ep, gain = job
    s, df, _ = episode(wfile, sour, headroom, ep, gain)
    return summarise(s, df, ep)


def trace(df):
    cols = {c: df[c] for c in ("frame", "x", "y", "air", "threat_kind", "threat_id") if c in df}
    out = pd.DataFrame(cols)
    out["theta_deg"] = np.degrees(df.theta).round(2)
    for c in ("headroom_factor", "headroom_rise", "headroom_need", "sour_level", "mdn"):
        if c in df:
            out[c] = df[c].astype(float).round(5)
    for c in ("theta_unscaled", "sour_theta"):
        if c in df:
            out[c + "_deg"] = np.degrees(df[c].astype(float)).round(2)
    out["ttmn"], out["steer"], out["dnp09"] = df.ttmn.round(4), df.steer.round(5), df.dnp09.round(4)
    out["driver"] = df.driver
    for c in ("a", "right", "left", "backup", "powerup", "blocks_hit", "score", "lives", "enemy_slots"):
        if c in df:
            out[c] = df[c]
    out["buttons"] = df.buttons
    return out


def main():
    cmd, tag, wfile, sour, headroom = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    gain = float(sys.argv[6]) if len(sys.argv) > 6 else None
    if cmd == "holdout":
        from . import episodes4
        eps = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
        with mp.get_context("spawn").Pool(6) as pool:
            res = pool.map(_job, [(wfile, sour, headroom, e, gain) for e in eps])
        json.dump(dict(tag=tag, wfile=wfile, sour=sour, headroom=headroom, gain=gain, episodes=res), open(ROOT / "runs" / f"AV1_{tag}_holdout.json", "w"), indent=1, default=float)
        for r in res:
            print(r["noop_start"], r["sigma"], "flag" if r["flag"] else "DIED", r["max_x"], r["cause"], "blocks", r["n_blocks"], "mush", r["mushroom_eaten"], "backup presses", r["backup_presses"], "traj", r["traj"], flush=True)
        print("flags", sum(r["flag"] for r in res), "/ 10; mean max_x", np.mean([r["max_x"] for r in res]), "backup frames", sum(r["backup_frames"] for r in res))
    elif cmd == "level12" or cmd == "scene":
        os.environ["FLYRUN_LEVEL"] = "1-2"
        ep = dict(noop_start=0, seed=0, sigma=0.0)
        tk = int(os.environ["AV1_TAKEOVER"]) if cmd == "scene" else None
        if tk is not None:
            from . import scripted
            scripted.Driver = ReplayDriver      # ASSISTED / diagnostic: the scripted player walks him to x >= tk (grounded), then the fly takes over
        s, df, k = episode(wfile, sour, headroom, ep, gain, takeover_x=tk)
        r = summarise(s, df, ep)
        r["tag"], r["takeover_x"] = tag, tk
        deaths = r["cause"]
        trace(df).to_csv(ROOT / "runs" / f"AV1_{tag}_{'12' if cmd == 'level12' else 'scene'}_trace.csv", index=False, lineterminator="\n")
        json.dump(r, open(ROOT / "runs" / f"AV1_{tag}_{'12' if cmd == 'level12' else 'scene'}.json", "w"), indent=1, default=float)
        print(tag, "max_x", r["max_x"], "flag", r["flag"], "end", r["end"], "cause", r["cause"], "x_end", r["x_end"], "frames", r["frames"], "blocks", r["n_blocks"], "mushroom", r["mushroom_eaten"], "backup frames", r["backup_frames"], "presses", r["backup_presses"])


if __name__ == "__main__":
    main()
