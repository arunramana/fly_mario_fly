"""L2b facts: every structure the NEW scanner reads in World 1-2 (walls / pipes / steps as faces, pits, and what hangs above him), along the L2 scan traversal (arm A, enemies removed, pit rescue).
Per world column, as first seen: the face height from level.scan_visible(rim=True), and level.headroom() for a small Mario standing on the floor there (feet 176):
(ceiling_y, rise). Output: runs/L2b_structures.csv (one row per structure), runs/L2b_columns.csv (per column).
python -m flyrun.l2b_structures"""
import os

os.environ["FLYRUN_LEVEL"] = "1-2"
from dataclasses import replace
from pathlib import Path

import pandas as pd

from . import c1_run as C
from . import level
from .run import _get_env, run_episode

ROOT = Path(__file__).resolve().parent


def main():
    env = _get_env()
    new_sets = {k: set(v) for k, v in level.EXTRA_WALL.items()}
    ram = env.unwrapped.ram
    orig = env.step
    wall, pit, head = {}, {}, {}
    fix = {}

    def step(a):
        out = orig(a)
        for s in range(5):
            ram[0x0F + s] = 0
        if int(ram[0x00CE]) > 200 and int(ram[0x00B5]) == 1:
            ram[0x00CE], ram[0x009F], ram[0x00B5] = 120, 0, 1
        level.EXTRA_WALL.update({k: set(v) for k, v in new_sets.items()})       # record with the NEW decoding ...
        w, p = level.scan_visible(ram, rim=True)
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        for x, h in w:
            wall[x] = h
        for x, wd in p:
            pit[x] = max(pit.get(x, 0), wd)
        if not fix and left + 240 >= 960:                              # real tile columns around the x ~ 890 hanging pillar, for the unit test (tests/test_l2b.py)
            fix.update({str(wx): [level.tile(ram, wx, r) for r in range(13)] for wx in range(832, 960, 16)})
        for wx in range(((left + 16) // 16) * 16, left + 240, 16):
            if wx not in head:
                head[wx] = level.headroom(ram, wx + 2, wx + 14, 176, 16)
        level.EXTRA_WALL["1-2"] = set()                                           # ... but let the fly walk with the L2 perception so the scan reaches the end
        return out
    env.step = step
    level.EXTRA_WALL["1-2"] = set()
    k = replace(C.KN, **C.ARMS["A"])
    s, df = run_episode(k, C._brain(), noop_start=0, stuck_frames=600, max_frames=12000)
    import json
    json.dump(fix, open(ROOT / "runs" / "L2b_fixture_1-2_x832_960.json", "w"))
    cols = pd.DataFrame([dict(x=x, face_h=wall.get(x, 0), pit_w_from_here=pit.get(x, 0), ceiling_y=c, rise=r) for x, (c, r) in sorted(head.items())])
    cols.to_csv(ROOT / "runs" / "L2b_columns.csv", index=False, lineterminator="\n")
    rows = []
    prev = None                      # merge neighbouring columns of the same face height
    for x in sorted(wall):
        if prev and x == prev["x1"] and wall[x] == prev["h"]:
            prev["x1"] = x + 16
        else:
            prev = dict(kind="face", x0=x, x1=x + 16, h=wall[x])
            rows.append(prev)
    rows = [dict(kind=r["kind"], x0=r["x0"], x1=r["x1"], h=r["h"]) for r in rows]
    end = -1
    for x in sorted(pit):
        if x >= end:
            rows.append(dict(kind="pit", x0=x, x1=x + pit[x], h=pit[x]))
            end = x + pit[x]
    low = cols[(cols.rise < 68) & (cols.face_h == 0)]      # columns inside a wall are the wall, not a ceiling
    prev = None
    for r in low.itertuples():
        if prev and r.x == prev["x1"] and r.rise == prev["rise"] and r.ceiling_y == prev["ceiling_y"]:
            prev["x1"] = r.x + 16
        else:
            prev = dict(kind="low_ceiling", x0=r.x, x1=r.x + 16, h=r.rise, ceiling_y=r.ceiling_y, rise=r.rise)
            rows.append(prev)
    out = pd.DataFrame(rows).sort_values("x0")
    out.to_csv(ROOT / "runs" / "L2b_structures.csv", index=False, lineterminator="\n")
    print(out.to_string(index=False))
    print("max_x", s["max_x"], s["end_reason"])


if __name__ == "__main__":
    main()
