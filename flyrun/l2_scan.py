"""L2 facts only (not the fly's scored result): play World 1-2 with the fly (arm A or C) but with the ENEMIES REMOVED (RAM poke after every step, as in O0), to separate terrain failures from enemy
failures and to census what the level contains as far as he gets. python -m flyrun.l2_scan [A|C]"""
import os

os.environ["FLYRUN_LEVEL"] = "1-2"
import json
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from . import c1_run as C
from .l2_run import Probe2
from .run import _get_env, run_episode

ROOT = Path(__file__).resolve().parent
RESCUE = "rescue" in sys.argv[2:]
STAR = "star" in sys.argv[2:]
SUF = os.environ.get("L2_SUFFIX", "")   # L2b: re-run with the new scanner without overwriting the L2 files


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else "A"
    env = _get_env()
    ram = env.unwrapped.ram
    orig = env.step

    rescued, shots, last, changes, area, firsts, dbg = [], {}, [None], [], [None], {}, []

    def step(a):
        out = orig(a)
        if STAR:
            ram[0x079F] = 0x30                                          # facts only: star-invincible, enemies stay (census of enemy type bytes)
        else:
            for s in range(5):
                ram[0x0F + s] = 0
        if RESCUE and int(ram[0xCE]) > 200 and int(ram[0x00B5]) == 1:     # facts only: lift him out of a pit so the scan can continue past it
            rescued.append(int(ram[0x006D]) * 256 + int(ram[0x0086]))
            ram[0xCE], ram[0x009F], ram[0x00B5] = 120, 0, 1
        xx = int(ram[0x006D]) * 256 + int(ram[0x0086])
        for th in (1200, 1900, 2200, 2450, 2550, 2650, 2750, 2800, 3000, 3100):
            if xx >= th and th not in shots:
                shots[th] = np.asarray(out[0]).copy()
        for sl in range(5):
            if int(ram[0x0F + sl]):
                ty = int(ram[0x16 + sl])
                if ty not in firsts:
                    firsts[ty] = dict(mario_x=xx, enemy_x=int(ram[0x6E + sl]) * 256 + int(ram[0x87 + sl]), enemy_y=int(ram[0xCF + sl]), state=int(ram[0x1E + sl]))
                    if STAR:
                        cv2.imwrite(str(ROOT / "clips" / "L2_stills" / f"enemy_type{ty}{SUF}.png"), cv2.cvtColor(cv2.resize(np.asarray(out[0]), None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR))
        if xx >= 1866 and not dbg:
            from . import level as LV
            dbg.append({str(wx): [LV.tile(ram, wx, r) for r in range(6, 13)] for wx in range(1840, 1990, 16)})
        ar = int(ram[0x074E])
        if ar != area[0]:
            changes.append(dict(x=xx, feet=int(ram[0xCE]), area_from=area[0], area_to=ar, player_state=int(ram[0x000E]), screen=int(ram[0x071A]) * 256 + int(ram[0x071C]), pipe_timer=int(ram[0x0722])))
            area[0] = ar
        last[0] = (np.asarray(out[0]).copy(), dict(x=xx, world=int(ram[0x075F]) + 1, level=int(ram[0x0760]) + 1, area=int(ram[0x074E]), player_state=int(ram[0x000E]), mode=int(ram[0x0770]), info=dict(out[3])))
        return out
    env.step = step
    pr = Probe2()
    k = replace(C.KN, **C.ARMS[arm])
    s, df = run_episode(k, C._brain(), noop_start=0, stuck_frames=300, probe=pr, max_frames=9000)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k, True)
    C.trace_cols(df).to_csv(ROOT / "runs" / f"L2_scan_{arm}{'_rescue' if RESCUE else ''}{'_star' if STAR else ''}{SUF}.csv", index=False, lineterminator="\n")
    out = dict(arm=arm, max_x=s["max_x"], end=s["end_reason"], cause=s["cause"], x_end=s["x_at_end"], frames=s["frames"], score=s["score"], tiles={f"r{r}_t{t}": n for (r, t), n in sorted(pr.tiles.items())},
               pits=sorted(pr.pits), enemies={f'type{t}_state{st}': n for (t, st), n in sorted(pr.enemies.items())}, rescued_at=sorted(set(rescued)), area_changes=changes, dbg_tiles_rows6_12=dbg, first_seen=firsts, blocks_hit=[h["block_x"] for h in pr.hits])
    for th, im in list(shots.items()) + [("end", last[0][0])]:
        cv2.imwrite(str(ROOT / "clips" / "L2_stills" / f"scan_x{th}{SUF}.png"), cv2.cvtColor(cv2.resize(im, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR))
    out["end_state"] = {k: (v if k != "info" else {a: (b if not hasattr(b, "item") else b.item()) for a, b in v.items()}) for k, v in last[0][1].items()}
    json.dump(out, open(ROOT / "runs" / f"L2_scan_{arm}{'_rescue' if RESCUE else ''}{'_star' if STAR else ''}{SUF}.json", "w"), indent=1)
    print(json.dumps(out)[:2500])


if __name__ == "__main__":
    main()
