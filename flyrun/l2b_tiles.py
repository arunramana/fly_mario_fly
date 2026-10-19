"""L2b facts (not the fly's scored result): which 1-2 tile ids are SOLID, tested on the emulator, and the hitbox of every enemy type seen.
Traversal = L2's scan (arm A, enemies removed, pit rescue; reached the flag in L2). Whenever a tile id not yet decided has a cell on screen with room around it,
the emulator is backed up, Mario is poked next to it, the game runs a few frames, and the state is restored (so the traversal is untouched).
Tests (small Mario, SMB's own collision): DROP = feet 3 px above the cell's top, falling: solid if he lands on it; BUMP = head just under the cell, moving up: solid if the
rise stops; SIDE = body level with the cell, walking Right into it with y frozen: solid if x is blocked. python -m flyrun.l2b_tiles [1-2|1-1]  -> runs/L2b_tiles.json (+ clips/L2_stills/l2b_tile<id>.png, gitignored)"""
import os

import sys

LV = sys.argv[1] if len(sys.argv) > 1 else "1-2"
os.environ["FLYRUN_LEVEL"] = LV
import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from . import c1_run as C
from . import level
from .run import _get_env, run_episode

ROOT = Path(__file__).resolve().parent
RIGHT, A = 128, 1
TILE = 16


def cell_ok(ram, wx, r):
    return 0 <= r <= 12 and level.tile(ram, wx, r) == 0


def wipe(ram, wx, rows):
    """Empty buffer cells (inside a backup only, restored afterwards) so every cell can be tested whatever stands around it."""
    for q in rows:
        if 0 <= q <= 12:
            ram[level.BUF + level.PAGE_BYTES * ((wx // 256) % 2) + 16 * q + (wx % 256) // TILE] = 0


def poke_mario(ram, wx_left, feet, vy=0):
    left = int(ram[0x071A]) * 256 + int(ram[0x071C])
    ram[0x006D], ram[0x0086] = (wx_left >> 8) & 0xFF, wx_left & 0xFF
    ram[0x03AD] = (wx_left - left) & 0xFF
    ram[0x00CE], ram[0x009F] = feet, vy & 0xFF
    ram[0x001D] = 1                         # airborne
    ram[0x0433] = 0                         # vertical force fraction


def probe(env, ram, wx, r):
    """-> dict of test results for the cell (wx, r); each None if the neighbourhood did not allow that test."""
    out = {}
    adv = env.unwrapped._frame_advance
    big = int(ram[0x0756]) >= 1
    mh = 24 if big else 16
    rows_h = mh // TILE + 1
    # DROP: cells above (rows r-1 .. r-rows_h) in this column empty
    if True:
        env.unwrapped._backup()
        wipe(ram, wx, range(r - rows_h, r))
        poke_mario(ram, wx + 2, TILE * r - 3)
        tr = []
        for _ in range(10):
            adv(0)
            tr.append((int(ram[0x00CE]), int(ram[0x001D])))
        out["drop"] = dict(solid=bool(0 <= tr[-1][0] - TILE * r <= 6), trace=tr[-4:])   # lands within 6 px of the top (free fall would be 20+ px lower)
        env.unwrapped._restore()
    # BUMP: head under the cell: the body occupies rows r+1 .. ; those cells empty
    if True:
        env.unwrapped._backup()
        wipe(ram, wx, range(r + 1, r + 1 + rows_h))
        feet0 = TILE * (r + 1) + mh
        poke_mario(ram, wx + 2, feet0, vy=0xFC)
        ys = []
        for _ in range(4):
            adv(0)
            ys.append(int(ram[0x00CE]))
        out["bump"] = dict(solid=bool(ys[1] >= ys[0] and ys[2] >= ys[0]), feet=ys)   # free flight keeps rising for several frames; a hit stops the rise at once
        env.unwrapped._restore()
    # SIDE: body level with this cell (feet at the bottom of the cell's row), cell to his left empty over his height
    rows = range(r, r - mh // TILE, -1) if mh > 16 else [r]
    if True:
        env.unwrapped._backup()
        for dx in (1, 2):
            wipe(ram, wx - dx * TILE, rows)
        x0 = wx - 14
        for i in range(12):
            poke_mario(ram, x0 if i == 0 else int(ram[0x006D]) * 256 + int(ram[0x0086]), TILE * (r + 1))
            adv(RIGHT)
        xe = int(ram[0x006D]) * 256 + int(ram[0x0086])
        out["side"] = dict(solid=bool(xe + 12 <= wx + 1), x_end_right_edge=xe + 12, cell_x=wx)
        env.unwrapped._restore()
    return out


def probe_as(env, ram, wx, r, tid):
    """Write tile id `tid` into an EMPTY cell (inside a backup) and run the same probe on it: tests ids that are rarely on screen (35 bumped ?-block, 196 used block)."""
    addr = level.BUF + level.PAGE_BYTES * ((wx // 256) % 2) + 16 * r + (wx % 256) // TILE
    old = int(ram[addr])
    ram[addr] = tid
    res = probe(env, ram, wx, r)          # each test backs up / restores the emulator itself, to the state with the id written
    ram[addr] = old                        # so put the cell back
    return res


def main():
    # the traversal only needs the fly to get through the level; with the 1-2 bricks decoded he stops at the exit wall (L2b.md), so walk it with the L2 perception (the
    # probes below read tiles / RAM directly and do not depend on these sets)
    level.EXTRA_WALL["1-2"] = set()
    forced = {}
    env = _get_env()
    ram = env.unwrapped.ram
    orig = env.step
    seen = {}          # id -> list of (wx, r) cells (all)
    verdict = {}       # id -> list of probe dicts
    shots = {}
    state = dict(busy=False)
    done = set()
    frame_no = [0]

    def step(a):
        out = orig(a)
        if state["busy"]:
            return out
        for s in range(5):
            ram[0x0F + s] = 0
        if int(ram[0x00CE]) > 200 and int(ram[0x00B5]) == 1:         # pit rescue (facts only)
            ram[0x00CE], ram[0x009F], ram[0x00B5] = 120, 0, 1
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        if not forced and frame_no[0] > 40 and level.tile(ram, left + 160, 5) == 0:
            state["busy"] = True
            try:
                for tid in (0, 35, 196, 194):
                    forced[tid] = probe_as(env, ram, ((left + 160) // TILE) * TILE, 5, tid)
            finally:
                state["busy"] = False
        frame_no[0] += 1
        for wx in range(((left + 32) // TILE) * TILE, left + 256 - 48, TILE):
            for r in range(13):
                t = level.tile(ram, wx, r)
                if not t:
                    continue
                cells = seen.setdefault(t, [])
                if (wx, r) not in cells and len(cells) < 400:
                    cells.append((wx, r))
                if t not in shots and t not in (84, 82, 18, 19, 20, 21, 97, 192, 193, 194):
                    shots[t] = (wx - left, r, np.asarray(out[0]).copy())
                v = verdict.setdefault(t, [])
                if len(v) < 8 and (wx, r) not in done and sum(1 for p in v if p["cell"][1] == r) < 2:
                    state["busy"] = True
                    try:
                        res = probe(env, ram, wx, r)
                    finally:
                        state["busy"] = False
                    if res:
                        done.add((wx, r))
                        v.append(dict(cell=(wx, r), **res))
        return out
    env.step = step
    k = replace(C.KN, **C.ARMS["A"])
    s, df = run_episode(k, C._brain(), noop_start=0, stuck_frames=400, max_frames=9000)
    summary = {}
    for t, v in sorted(verdict.items()):
        votes = [x["solid"] for p in v for key, x in p.items() if key in ("drop", "bump", "side")]
        summary[int(t)] = dict(n_cells=len(seen[t]), rows=sorted({r for _, r in seen[t]}), x_first=min(w for w, _ in seen[t]), x_last=max(w for w, _ in seen[t]),
                               n_tests=len(votes), n_solid=int(sum(votes)), tests=v[:6])
    for t in seen:
        summary.setdefault(int(t), dict(n_cells=len(seen[t]), rows=sorted({r for _, r in seen[t]}), x_first=min(w for w, _ in seen[t]), x_last=max(w for w, _ in seen[t]), n_tests=0, n_solid=0, tests=[]))
    for t, (sx, r, im) in shots.items():
        im = cv2.resize(np.asarray(im), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.rectangle(im, (sx * 3 - 2, (r * TILE + 32) * 3 - 2), (sx * 3 + 50, (r * TILE + 32) * 3 + 50), (255, 0, 0), 2)
        cv2.imwrite(str(ROOT / "clips" / "L2_stills" / f"l2b_{LV}_tile{t}.png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
    json.dump(dict(max_x=s["max_x"], end=s["end_reason"], tiles=summary, forced={str(k): v for k, v in forced.items()}),
              open(ROOT / "runs" / ("L2b_tiles.json" if LV == "1-2" else f"L2b_tiles_{LV}.json"), "w"), indent=1, default=int)
    for t, v in summary.items():
        print(t, "cells", v["n_cells"], "rows", v["rows"], "x", v["x_first"], "-", v["x_last"], "tests", v["n_tests"], "solid", v["n_solid"])
    print("max_x", s["max_x"], s["end_reason"])


if __name__ == "__main__":
    main()
