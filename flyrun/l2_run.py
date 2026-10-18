"""Part L2: the current fly (881-neuron brain, frozen gains, no changes) on World 1-2. FLYRUN_LEVEL=1-2 selects the level in env.make_env; everything else is the 1-1 code, untouched.
python -m flyrun.l2_run facts   -> a census of tile ids / enemy types / pits seen while arm A and arm C play (runs/L2_census.json)
python -m flyrun.l2_run runs    -> arm A + arm C noop 0 (logs for the videos) and the 10 HOLDOUT episodes of arm A (runs/L2_*.csv, runs/L2_arms.json)"""
import os

os.environ["FLYRUN_LEVEL"] = "1-2"
import json
import multiprocessing as mp
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from . import c1_run as C
from . import episodes4
from . import level

ROOT = Path(__file__).resolve().parent


class Probe2(C.Probe):
    """C1's probe with the '?' blocks found from the tile buffer instead of the 1-1 table, plus a census of what the level contains (tile ids by row, enemy type bytes)."""

    def __init__(self):
        super().__init__()
        self.tiles, self.enemies, self.pits = Counter(), Counter(), set()

    def __call__(self, ram):
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        mx = int(ram[0x006D]) * 256 + int(ram[0x0086])
        for wx in range((left // 16) * 16, left + 256, 16):
            for row in range(13):
                t = level.tile(ram, wx, row)
                if t:
                    self.tiles[(row, t)] += 1 if (wx // 16) % 4 == 0 else 0
                if t in (192, 193):
                    self.seen.add((wx, row))
                elif t in (35, 196) and (wx, row) in self.seen:
                    self.seen.discard((wx, row))
                    self.hits.append(dict(block_x=wx, row=row, frame=self.f, mario_x=mx))
        for s in range(5):
            if int(ram[0x0F + s]):
                self.enemies[(int(ram[0x16 + s]), int(ram[0x1E + s]))] += 1
        _, pits = level.scan_visible(ram, rim=True)
        self.pits |= {p for p in pits}
        on = int(ram[0x0F + 5]) and int(ram[0x16 + 5]) == 0x2E
        out = dict(screen_left=left, powerup=int(ram[0x0756]), coins=int(ram[0x075E]), mush_x=(int(ram[0x6E + 5]) * 256 + int(ram[0x87 + 5])) if on else np.nan, blocks_hit=len(self.hits))
        self.f += 1
        return out


C.Probe = Probe2


def _job(job):
    arm, ep, tag = job
    s, df = C.episode(arm, ep)
    df.attrs["hits"] = df.attrs["hits"]
    C.trace_cols(df).to_csv(ROOT / "runs" / f"L2_{tag}.csv", index=False, lineterminator="\n")
    r = C.analyse(s, df, ep)
    r["arm"], r["tag"], r["toggles"] = arm, tag, df.attrs["toggles"]
    return r


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "runs"
    ep0 = dict(noop_start=0, seed=0, sigma=0.0)
    if what == "runs":
        from .render import log as RL
        jobs = [("A", ep0, "A_0_0.0"), ("C", ep0, "C_0_0.0")]
        eps = [dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT]
        jobs += [("A", e, f"A_{e['noop_start']}_{e['sigma']}") for e in eps]
        with mp.get_context("spawn").Pool(6) as pool:
            res = pool.map(_job, jobs)
        json.dump(res, open(ROOT / "runs" / "L2_arms.json", "w"), indent=1, default=float)
        for r in res:
            print(r["tag"], "max_x", r["max_x"], "flag", r["flag"], r["end"], r["cause"], "x_end", r["x_end"], "blocks", r["blocks_hit"], "score", r["score"], flush=True)
        for arm in "AC":
            RL.run_log(arm, f"arm{arm}", prefix="L2")
    else:
        out = {}
        for arm in "AC":
            pr = Probe2()
            from .run import run_episode
            from dataclasses import replace
            k = replace(C.KN, **C.ARMS[arm])
            s, df = run_episode(k, C._brain(), noop_start=0, stuck_frames=150, probe=pr, max_frames=3000)
            out[arm] = dict(max_x=s["max_x"], end=s["end_reason"], tiles={f"r{r}_t{t}": n for (r, t), n in sorted(pr.tiles.items())}, enemies={f"type{t}_state{st}": n for (t, st), n in sorted(pr.enemies.items())},
                            pits=sorted(pr.pits))
        json.dump(out, open(ROOT / "runs" / "L2_census.json", "w"), indent=1)
        print(json.dumps(out)[:3000])


if __name__ == "__main__":
    main()
