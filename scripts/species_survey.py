"""species_survey.py -- REFACTOR_PLAN.md phase 4: what ADDR_ENEMY_TYPE
byte values actually appear in 1-1 and 1-2? Checked empirically, not
assumed from memory or a web table -- same standard mario/ram/tile_ram.py's
own tile IDs were held to (cross-check against a captured screenshot).

The real circuit (run_steering.main()) dies too early to see much of
either level -- deterministically, at sigma=0, every seed reaches exactly
the same point (1-1: frame 689/x=1432; 1-2: frame 84/x=184). This script
bypasses the circuit entirely: hold right, mash jump on a randomised duty
cycle, so Mario physically clears most ground obstacles and reaches much
further before dying. This is a species census, not a circuit-behaviour
test -- the bot's own trajectory means nothing.

Confirmed by this script, screenshot-verified, docs/ENTITIES.md's phase 4
section has the full report:
  0x06 = Goomba  (1-1 frame ~60, 1-2 frame ~0)
  0x00 = Koopa   (1-2 underground section, abs_x~709; corroborates
                  sprint 010's own independent manual RAM-inspection ID)

A third type byte, 0x0D, appeared further into 1-2 (abs_x~1400) but could
NOT be visually confirmed within a screenshot before it scrolled off --
correctly left classified as generic ENEMY rather than guessed. Same
standard as tile_ram.py: a real, checked byte value without independent
visual corroboration is reported as "found, not yet identified," not
silently named from memory.

1-1, surveyed to abs_x=1522 (beyond the real circuit's own x=1432 death
point), is entirely Goombas. Not exhaustive -- a species this survey
didn't reach may still exist further into either level.

    .venv/Scripts/python.exe -m scripts.species_survey
"""
from __future__ import annotations

import numpy as np

from mario.actions.actions import action_index
from mario.emulator.env import make_env
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE,
    ADDR_MARIO_X, N_ENEMY_SLOTS, POWERUP_ID,
)

RIGHT_A_B = action_index("R", True, True)
RIGHT_B = action_index("R", False, True)


def survey(level: str, total_frames: int = 200_000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    env = make_env(level)
    obs = env.reset()
    ram = env.unwrapped.ram
    seen: dict[int, tuple[int, int, int]] = {}
    max_abs_x = 0
    n_resets = 0
    on_frames, off_frames = int(rng.integers(4, 20)), int(rng.integers(2, 10))
    life_frame = 0

    for frame in range(total_frames):
        cycle = on_frames + off_frames
        action = RIGHT_A_B if (life_frame % cycle) < on_frames else RIGHT_B
        for i in range(N_ENEMY_SLOTS):
            if ram[ADDR_ENEMY_ACTIVE + i] == 0:
                continue
            t = int(ram[ADDR_ENEMY_TYPE + i])
            if t == POWERUP_ID or t in seen:
                continue
            abs_x = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_ENEMY_X + i])
            seen[t] = (frame, abs_x, n_resets)
            print(f"  [{level}] NEW type=0x{t:02X} at frame {frame} (life #{n_resets}), abs_x~={abs_x}")
        max_abs_x = max(max_abs_x, int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X]))
        obs, reward, done, info = env.step(action)
        life_frame += 1
        if done:
            n_resets += 1
            obs = env.reset()
            on_frames, off_frames = int(rng.integers(4, 20)), int(rng.integers(2, 10))
            life_frame = 0
    env.close()
    print(f"  {level}: {n_resets} lives used, max_abs_x reached = {max_abs_x}")
    print(f"  {level}: distinct non-powerup types = {sorted('0x%02X' % t for t in seen)}")
    return seen


if __name__ == "__main__":
    for lvl in ("1-1", "1-2"):
        print(f"=== {lvl} ===")
        survey(lvl)
