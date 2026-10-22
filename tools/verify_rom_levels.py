"""Check the level database against the emulator.

For each level given, Mario is carried through it (enemies swept every frame, a star timer keeps him alive, a Mario who
falls into a pit is put back on top of the screen a little further on) and the emulator is compared with
mario/facts/level_db.json:
  * tiles    every visible column of the game's tile buffer against the db's solid mask of the main area
  * spawns   every enemy / lift / fire bar the game spawns against the db's list (same id, x and y within one tile)
  * flag     the x where the game reports flag_get against the db's flag / axe x
Usage:  python tools/verify_rom_levels.py 1-1 1-2 1-4 2-2 [--frames 9000] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys

from fly_mario.mario import leveldata, ram as RM
from fly_mario.mario.env import MarioEnv
from fly_mario.mario.walker import Walker

PLAYER_Y_HIGH, PLAYER_Y, PLAYER_YSPEED, PLAYER_PAGE, PLAYER_X, STAR_TIMER = 0x00B5, 0x00CE, 0x009F, 0x006D, 0x0086, 0x079F
TOL = 16
DYNAMIC = (0x0A, 0x0B, 0x08, 0x12, 0x14, 0x15, 0x16, 0x2E, 0x2F, 0x30, 0x31, 0x33)     # made at run time (flames, bills, thrown spinies, power-ups, flags)


def stage_expectations(stage: dict, area: dict) -> list:
    """What the game should spawn in this stage's main area: [(id, x, ram_y, approx, label)]."""
    exp = []
    for key in ("enemies", "platforms", "firebars", "frenzy"):
        for e in area[key]:
            if e["hard_only"] and not stage["hard_mode"]:
                continue
            if e.get("never_spawns") or (e.get("from_pipe") and stage["no_pipe_piranha"]):
                continue
            exp.append((e["id"], e.get("ram_x", e["x"]), e["ram_y"], bool(e.get("approx_x")), e["type"]))
    return exp


def run_level(level: str, frames: int) -> dict:
    db = leveldata.load()
    stage = db["stages"][level]
    area = db["areas"][stage["main"]]
    mask = [int(area["solid"][i:i + 4], 16) for i in range(0, len(area["solid"]), 4)]
    coin_cells = {(c["x"] // 16 + k, c["row"]) for c in area["coins"] for k in range(c["w"])}
    env = MarioEnv()
    env.reset(level, "v0", 0)
    facts, r = env.facts, env.facts["ram"]
    walker = Walker()
    seen_ids = [None] * 5
    spawns, mism, cells, max_x, flag_x, stop = [], {}, 0, 0, None, "frames"
    trail, hold = [], 0
    prev_x, area_no, best_x, best_i = 0, int(env.ram[0x0760]), 0, 0
    for s0, typ, state, ex, ey in RM.active_slots(env.ram, facts):
        spawns.append((0, s0, typ, ex, ey))
        seen_ids[s0] = (typ, ex // 8)
    for i in range(frames):
        RM.sweep_enemies(env, facts)
        act = walker.act(env)
        if hold:
            act, hold = (("right",) if hold == 46 else ("right", "A", "B")), hold - 1
        if area["area_type"] == "water" and not hold:
            act = ("right", "A") if (i % 10 == 0 or int(ram[PLAYER_Y]) > 0x90) else ("right",)
        st = env.step(act)
        env.poke(STAR_TIMER, 0x20)
        ram = env.ram
        x = RM.mario_x(ram, facts)
        trail = (trail + [(i, x, int(ram[PLAYER_Y]), int(ram[PLAYER_Y_HIGH]), int(ram[facts['ram']['player_state']]), int(ram[0x000E]))])[-12:]
        if int(ram[0x0760]) != area_no or x + 200 < prev_x:
            stop = f"area changed (area {area_no}->{int(ram[0x0760])}, x {prev_x}->{x}, y {int(ram[PLAYER_Y])}, yh {int(ram[PLAYER_Y_HIGH])})"
            break
        prev_x = max(prev_x, x)
        max_x = max(max_x, x)
        if st.info.get("flag_get"):
            flag_x, stop = x, "flag"
            break
        if st.done:
            stop = "died"
            break
        if i % 60 == 0:
            env.poke(0x07F8, 9)                    # keep the level timer from running out
        if x > best_x:
            best_x, best_i = x, i
        if int(ram[PLAYER_Y_HIGH]) == 1 and int(ram[PLAYER_Y]) > 0xB8 and int(ram[facts["ram"]["player_state"]]) != 0:
            env.poke(PLAYER_Y, 0xA8)               # over a pit: hold Mario at ground level so he glides across
            env.poke(PLAYER_YSPEED, 0)
        if i - best_i > 20 and not hold and int(ram[facts["ram"]["player_state"]]) != 0:
            env.poke(PLAYER_Y, 0x58)               # stuck in the air (floating over a pit beside a wall): rise above it
            env.poke(PLAYER_YSPEED, 0)
            best_i = i
        elif i - best_i > 20 and not hold:
            hold = 46                              # stuck at a wall: one full-height running jump
            best_i = i
        for s, typ, state, ex, ey in RM.active_slots(ram, facts):
            if seen_ids[s] != (typ, ex // 8):
                if seen_ids[s] is None or seen_ids[s][0] != typ or abs(seen_ids[s][1] * 8 - ex) > 24:
                    spawns.append((i, s, typ, ex, ey))
            seen_ids[s] = (typ, ex // 8)
        for s in range(5):
            if not int(ram[r["enemy_active"] + s]):
                seen_ids[s] = None
        if i % 4 == 0:
            for wx in RM.visible_columns(ram, facts):
                c = wx // 16
                if c >= len(mask):
                    continue
                for row in range(13):
                    emu = RM.tile(ram, facts, wx, row)
                    cells += 1
                    if bool(emu) != bool(mask[c] >> row & 1) and emu not in (196, 35) and (c, row) not in coin_cells:
                        mism.setdefault((c, row), (emu, bool(mask[c] >> row & 1)))
    env.close()
    exp = stage_expectations(stage, area)
    lo, hi = 0, max_x - 40
    missing, matched = [], 0
    pool = list(spawns)
    for (eid, ex, ey, approx, label) in exp:
        if not (lo <= ex <= hi):
            continue
        tol = 56 if approx else TOL
        hit = next((s for s in pool if s[2] == eid and abs(s[3] - ex) <= tol and abs(s[4] - ey) <= TOL + (24 if eid in (0x25, 0x2B, 0x2C, 0x26, 0x27) else 0)), None)
        if hit:
            pool.remove(hit)
            matched += 1
        else:
            near = min((q for q in spawns if q[2] == eid), key=lambda q: abs(q[3] - ex), default=None)
            missing.append((label, eid, ex, ey, "nearest spawn: " + (f"x={near[3]} y={near[4]}" if near else "none")))
    extra = [(f, s, t, x, y) for f, s, t, x, y in pool if lo <= x <= hi and t not in DYNAMIC]
    flag_db = stage["width"]
    return {"level": level, "stop": stop, "max_x": max_x, "cells": cells, "tile_mismatches": sorted(mism.items())[:30],
            "n_tile_mismatches": len(mism), "expected": len([e for e in exp if lo <= e[1] <= hi]), "matched": matched,
            "missing": missing, "extra": extra[:30], "n_extra": len(extra), "emulator_flag_x": flag_x, "db_flag_x": flag_db, "db_flag_get_x": stage["flag_get_x"],
            "end_area": stage["end"] and stage["end"]["area"], "last": trail[-1] if trail else None, "spawns": spawns}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("levels", nargs="+")
    ap.add_argument("--frames", type=int, default=9000)
    ap.add_argument("--json")
    args = ap.parse_args()
    out = [run_level(lv, args.frames) for lv in args.levels]
    for o in out:
        print(f"{o['level']}: stop={o['stop']} max_x={o['max_x']} tiles {o['n_tile_mismatches']}/{o['cells']} mismatch; "
              f"spawns expected {o['expected']} matched {o['matched']} missing {len(o['missing'])} extra {o['n_extra']}; "
              f"flag_get emu={o['emulator_flag_x']} db={o['db_flag_get_x']} (pole/axe {o['db_flag_x']}) last={o['last']}")
        for m in o["missing"][:12]:
            print("   missing", m)
        for e in o["extra"][:12]:
            print("   extra  ", e)
        for t in o["tile_mismatches"][:8]:
            print("   tile   ", t)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
