"""Part 2: pipe + pit senses. Numbers go to runs/001_test_numbers.json (feeds runs/001_senses.md)."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from flyrun import env as E
from flyrun import level, scripted
from flyrun.knobs import Knobs
from flyrun.run import run_episode
from .conftest import NUMBERS2, record

RUNS = NUMBERS2.parent
PIPE1_FAR = 479     # nb 13: success = alive past this x
PIT_FAR = 1135      # nb 15
TAKEOVER_X = 1037   # nb 15


def rec(key, value):
    record(key, value, NUMBERS2)


def a_runs(a):
    d = np.diff(np.r_[0, np.asarray(a, dtype=int), 0])
    starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
    return ends - starts


def rising(df):
    return df[(df["a"] == 1) & (df["a"].shift(1, fill_value=0) == 0)]


@pytest.fixture(scope="module")
def level_map():
    """Scroll through 1-1 with the SCRIPTED driver (diagnostic) and decode what the buffer shows."""
    from flyrun.levelmap import scan_level
    df, best, flag = scan_level()
    df.to_csv(RUNS / "001_level_map.csv", index=False)
    print("LEVEL MAP (scripted scroll, reached x=%d, flag=%s)" % (best, flag))
    print(df.to_string(index=False))
    rec("level_map_reached_x", best)
    return df


def test_level_decode(level_map):
    walls = level_map[level_map.kind == "wall"]
    pits = level_map[level_map.kind == "pit"]
    p1 = walls[(walls.x - 448).abs() <= 8]
    assert len(p1) and int(p1.iloc[0]["size"]) == 32
    q1 = pits[(pits.x - 1104).abs() <= 8]
    assert len(q1) and int(q1.iloc[0]["size"]) == 32


def test_pipe_ab(brain):
    out = {}
    for name, on in (("off", False), ("on", True)):
        s, df = run_episode(replace(Knobs(), PIPE_SENSE=on, PIT_SENSE=False), brain, max_frames=3000)
        r = rising(df)
        pa = r[r["stim_src"] == "pipe"]
        runs = a_runs(df["a"])
        out[name] = dict(
            **s, A_frac=float(df["a"].mean()), longest_A_run=int(runs.max()) if len(runs) else 0,
            first_pipe_A_x=int(pa.iloc[0]["x"]) if len(pa) else None,
            first_pipe_A_d=float(pa.iloc[0]["stim_d"]) if len(pa) else None,
            cleared_pipe1=bool(s["max_x"] > PIPE1_FAR))
    rec("pipe_ab", out)
    assert 420 <= out["off"]["x_at_end"] <= 440 and out["off"]["end_reason"] == "stuck"
    assert out["on"]["first_pipe_A_x"] is not None and out["on"]["first_pipe_A_x"] < 448
    assert out["on"]["longest_A_run"] < 40


def test_pit_ab(brain):
    """ASSISTED: a scripted driver plays to x~1037 (nb 15's takeover), then the fly. Report only."""
    out = {}
    for name, on in (("off", False), ("on", True)):
        s, df = run_episode(replace(Knobs(), PIT_SENSE=on), brain, takeover_x=TAKEOVER_X, max_frames=4000)
        fly = df[df["driver"] == "fly"]
        r = rising(fly)
        pa = r[r["stim_src"] == "pit"]
        d = dict(**s, takeover_x=int(fly["x"].iloc[0]),
                 first_pit_A_x=int(pa.iloc[0]["x"]) if len(pa) else None,
                 first_pit_A_d=float(pa.iloc[0]["stim_d"]) if len(pa) else None,
                 cleared_pit1=bool(s["max_x"] > PIT_FAR and s["end_reason"] != "died" or s["max_x"] > PIT_FAR + 20))
        # jump distance: air stretches that start before the pit edge and where x crosses it
        air = fly[fly["air"] == 1]
        jumps = []
        grp = (fly["air"] != fly["air"].shift()).cumsum()
        for _, g in fly.groupby(grp):
            if g["air"].iloc[0] == 1 and len(g) > 3:
                jumps.append((int(g["x"].iloc[0]), int(g["x"].iloc[-1])))
        d["air_jumps_x"] = jumps[:12]
        out[name] = d
    rec("pit_ab", out)
    print("PIT A/B", out)


def test_death_map(brain):
    """Default run, everything on, fly only. Report: where does it stop and what is next to it."""
    s, df = run_episode(Knobs(), brain, max_frames=3000)
    ram = __import__("flyrun.run", fromlist=["_ENV"])._ENV.unwrapped.ram
    mx = E.mario_x(ram)
    enemies = []
    for sl in range(E.N_ENEMY_SLOTS):
        if int(ram[E.ADDR_ENEMY_ACTIVE + sl]) and int(ram[E.ADDR_ENEMY_TYPE + sl]) != E.POWERUP_ID:
            ex = int(ram[E.ADDR_ENEMY_PAGE + sl]) * 256 + int(ram[E.ADDR_ENEMY_X + sl])
            enemies.append(dict(slot=sl, type=hex(int(ram[E.ADDR_ENEMY_TYPE + sl])), x=ex, dx=ex - mx))
    r = rising(df)
    ev = r[["frame", "x", "stim_src", "stim_d", "theta"]].to_dict("records")
    last = df.tail(30)
    rec("death_map_default", dict(summary=s, mario_x_at_end=mx, mario_y=int(ram[0x00CE]),
                                  enemies_at_end=enemies, a_onsets=ev,
                                  src_last30=last["stim_src"].value_counts().to_dict(),
                                  a_last30=int(last["a"].sum())))
    runs = a_runs(df["a"])
    assert (runs.max() if len(runs) else 0) < 40
