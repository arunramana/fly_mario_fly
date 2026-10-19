"""L2b facts: the size of every enemy type seen in 1-2, from the sprite memory (OAM shadow 0x0200-0x02FF, 64 sprites of y, tile, attr, x), and the identity of type 0x03.
Traversal = L2's star-invincible scan (arm A, enemies stay, pit rescue). For each enemy slot alive, the sprites whose 8x8 tile lies within a window around the
object's position are grouped (Mario's own sprites excluded by his box); the union extent = the drawn size. The game's own hitbox bytes (0x04AC + 4 * object) are logged raw.
python -m flyrun.l2b_enemies -> runs/L2b_enemies.json, clips/L2_stills/l2b_enemy<type>.png"""
import os

os.environ["FLYRUN_LEVEL"] = "1-2"
import json
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

from . import c1_run as C
from .run import _get_env, run_episode

ROOT = Path(__file__).resolve().parent
ADDR_EY = 0x00CF


def oam(ram):
    return [(int(ram[0x0200 + 4 * i]), int(ram[0x0201 + 4 * i]), int(ram[0x0202 + 4 * i]), int(ram[0x0203 + 4 * i])) for i in range(64)]


def main():
    env = _get_env()
    ram = env.unwrapped.ram
    orig = env.step
    log, shots, info = {}, {}, {}
    plant, frame_no = [], [0]
    cnt, probing = {}, [False]

    def step(a):
        out = orig(a)
        frame_no[0] += 1
        ram[0x079F] = 0x30                                                   # star-invincible, enemies stay
        if int(ram[0x00CE]) > 200 and int(ram[0x00B5]) == 1:
            ram[0x00CE], ram[0x009F], ram[0x00B5] = 120, 0, 1
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        mxs = int(ram[0x03AD])                                                # Mario's x on screen
        sp = oam(ram)
        mario_y = int(ram[0x00CE])
        for s in range(5):
            if not int(ram[0x0F + s]):
                continue
            ty = int(ram[0x16 + s])
            ex = int(ram[0x6E + s]) * 256 + int(ram[0x87 + s])
            sx = ex - left                                                   # enemy x on screen
            if not (8 <= sx <= 240):
                continue
            ey = int(ram[ADDR_EY + s])                                       # RAM y = feet y + 8 (tile-buffer coordinates; screen y = this + 32 - 8... checked below)
            near = []
            if cnt.get(ty, 0) < 40 and not probing[0] and (cnt.get(ty, 0) < 12 or ty == 0x0D):
                probing[0] = True
                try:
                    env.unwrapped._backup()
                    for _ in range(3):                                      # the PPU draws the sprites built one frame earlier: look 3 frames ahead
                        env.unwrapped._frame_advance(0)
                    A = env.unwrapped.screen.copy().astype(int)
                    ex3 = int(ram[0x6E + s]) * 256 + int(ram[0x87 + s]) - (int(ram[0x071A]) * 256 + int(ram[0x071C]))
                    ey3 = int(ram[ADDR_EY + s])
                    env.unwrapped._restore()
                    ram[0x0F + s] = 0
                    for _ in range(3):
                        env.unwrapped._frame_advance(0)
                    B = env.unwrapped.screen.copy().astype(int)
                    env.unwrapped._restore()
                finally:
                    probing[0] = False
                ys_, xs_ = np.nonzero(np.abs(A - B).sum(axis=2) > 0)                  # the pixels the enemy draws (silhouette, not the 8x8 tile grid)
                if len(ys_):
                    cnt[ty] = cnt.get(ty, 0) + 1
                    near = [(int(ys_.min()), int(xs_.min()), int(ys_.max()) + 1, int(xs_.max()) + 1, ex3, ey3)]
            rec = log.setdefault(ty, {"n": 0, "samples": [], "states": {}})
            rec["n"] += 1
            st = str(int(ram[0x1E + s]))
            rec["states"][st] = rec["states"].get(st, 0) + 1
            if ty == 0x0D:                                                       # the plant's cycle: RAM y against the pipe it sits in
                plant.append((frame_no[0], ey, int(ram[0x1E + s]), sx, abs(sx - mxs)))
            if near:
                ext = None
                if near:
                    y0, x0, y1, x1, sx, ey = near[0]                              # screen px; tile-buffer y = screen y - 32; feet = RAM y - 8
                    ext = dict(w=x1 - x0, h=y1 - y0, x_left_of_ram_x=x0 - sx, top_above_feet=(ey - 8) - (y0 - 32), bottom_above_feet=(ey - 8) - (y1 - 32))
                rec["samples"].append(dict(state=int(ram[0x1E + s]), mario_x=int(ram[0x6D]) * 256 + int(ram[0x86]), ex=ex, ey=ey, hitbox_raw=[int(ram[0x04AC + 4 * (1 + s) + k]) for k in range(4)],
                                           mario_box_raw=[int(ram[0x04AC + k]) for k in range(4)], sprite_extent_rel_ram_xy=ext, spawn_flag=int(ram[0x0F + s])))
            if ty not in shots:
                shots[ty] = (sx, ey, np.asarray(out[0]).copy())
        return out
    env.step = step
    k = replace(C.KN, **C.ARMS["A"])
    s, df = run_episode(k, C._brain(), noop_start=0, stuck_frames=600, max_frames=12000)
    for t, (sx, ey, im) in shots.items():
        im = cv2.resize(np.asarray(im), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(ROOT / "clips" / "L2_stills" / f"l2b_enemy{t:02x}.png"), cv2.cvtColor(im, cv2.COLOR_RGB2BGR))
    json.dump(dict(max_x=s["max_x"], end=s["end_reason"], enemies={f"0x{t:02X}": v for t, v in sorted(log.items())}, plant_trace=plant[:400]), open(ROOT / "runs" / "L2b_enemies.json", "w"), indent=1)
    for t, v in sorted(log.items()):
        print(f"0x{t:02X}", v["n"], v["samples"][:2])
    print("max_x", s["max_x"], s["end_reason"])


if __name__ == "__main__":
    main()
