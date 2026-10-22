"""Hit blocks in the emulator and check what comes out against the level db's `contents`.

    python tools/verify_block_contents.py            # the default list below
A block is hit from below: Mario is carried next to it (enemies off, the walker), then jumps right under it. What came out is read
from RAM: the block's tile turns into the used block (196), and the power-up slot (5) holds a power-up object whose type byte
$0039 says mushroom (0), fire flower (1), star (2) or 1-up (3); a coin shows as the coin counter going up.
"""
from __future__ import annotations

import argparse
import sys

from fly_mario.mario import leveldata, ram as RM
from fly_mario.mario.env import MarioEnv
from fly_mario.mario.walker import walk_to

POWERUP_TYPE = 0x0039                    # PowerUpType: 0 mushroom, 1 fire flower, 2 star, 3 1-up
COINS = 0x075E
PLAN = [("1-1", 256, 7, "coin"), ("1-1", 336, 7, "power-up"), ("1-1", 1248, 7, "power-up"), ("1-1", 1616, 7, "star"),
        ("1-2", 160, 7, "power-up"), ("1-1", 1024, 6, "1-up")]


def hit(level: str, x: int, row: int, frames: int = 600) -> dict:
    env = MarioEnv()
    env.reset(level, "v0", 0)
    facts, r = env.facts, env.facts["ram"]
    walk_to(env, max(x - 40, 0))
    coins0, seen, tile0 = int(env.ram[COINS]), None, RM.tile(env.ram, facts, x, row)
    nx = x + 2                                              # stand right under the block, then jump straight up
    env.poke(0x006D, nx // 256)
    env.poke(0x0086, nx % 256)
    for i in range(frames):
        RM.sweep_enemies(env, facts)
        env.poke(0x0057, 0)                                  # no sideways speed: straight up
        act = ("A",) if 12 <= i < 40 else ()
        if env.step(act).done:
            break
        env.poke(0x079F, 0x20)
        if int(env.ram[r["enemy_active"] + 5]) and seen is None:
            seen = {"object": int(env.ram[r["enemy_type"] + 5]), "power_type": int(env.ram[POWERUP_TYPE])}
        if RM.tile(env.ram, facts, x, row) != tile0 and i > 4 and (seen or int(env.ram[COINS]) != coins0):
            break
    out = {"coins": int(env.ram[COINS]) - coins0, "powerup": seen}
    env.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    db = leveldata.load()
    bad = 0
    for level, x, row, want in PLAN:
        area = db["areas"][db["stages"][level]["main"]]
        block = next(b for b in area["blocks"] if (b["x"], b["row"]) == (x, row))
        got = hit(level, x, row)
        kind = "coin" if got["coins"] and not got["powerup"] else (
            {0: "power-up", 1: "power-up", 2: "star", 3: "1-up"}[got["powerup"]["power_type"]] if got["powerup"] else "nothing")
        ok = block["contents"] == want == kind
        bad += not ok
        print(f"{level} ({x}, row {row}): db says {block['contents']!r}, game gave {kind!r} {got} -> {'ok' if ok else 'MISMATCH'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
