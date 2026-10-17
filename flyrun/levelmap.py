"""Whole-level map of 1-1 from the tile buffer, scrolled with the SCRIPTED driver.
Test/diagnostic only: never part of fitness."""
import pandas as pd

from . import env as E
from . import level, scripted


def scan_level(max_frames=12000):
    """-> (DataFrame[kind, x, size], reached_x, flag_get)."""
    from .run import _get_env
    env = _get_env()
    env.reset()
    drv = scripted.Driver()
    walls, pits = {}, {}
    best, best_f, flag = 0, 0, False
    for f in range(max_frames):
        ram = env.unwrapped.ram
        w, p = level.scan_visible(ram)
        for x, h in w:
            walls[x] = h
        for x, wd in p:
            pits[x] = max(pits.get(x, 0), wd)
        _, _, done, info = env.step(drv.act(ram))
        mx = E.mario_x(ram)
        if mx > best:
            best, best_f = mx, f
        flag = bool(info.get("flag_get"))
        if done or flag or f - best_f > 300:
            break
    rows = []
    prev_x, prev_h = None, None   # adjacent columns of equal height are one face
    for x in sorted(walls):
        if prev_x is not None and x == prev_x + 16 and walls[x] == prev_h:
            prev_x = x
            continue
        rows.append(dict(kind="wall", x=x, size=walls[x]))
        prev_x, prev_h = x, walls[x]
    end = -1
    for x in sorted(pits):   # drop fragments clipped by the screen's left edge
        if x < end:
            continue
        rows.append(dict(kind="pit", x=x, size=pits[x]))
        end = x + pits[x]
    return pd.DataFrame(rows).sort_values("x").reset_index(drop=True), best, flag
