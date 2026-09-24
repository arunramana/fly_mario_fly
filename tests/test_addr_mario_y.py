"""mario/ram/addresses.py: ADDR_MARIO_Y was 0x00B5 ("_y_viewport" in
gym_super_mario_bros.smb_env's own source -- a coarse 0-5 viewport-region
flag, not a pixel position; confirmed constant at 1 across a full
689-frame run including 9 escape jumps). Fixed to 0x03B8 ("_y_pixel" in
that same source). This test is the direct proof: cross-checks the new
address against gym's own info['y_pos'], not just against the source
comment.
"""
from __future__ import annotations

import setuptools  # noqa: F401 -- must precede gym

from mario.emulator.env import make_env
from mario.ram.addresses import ADDR_MARIO_Y


def test_addr_mario_y_matches_gym_info_y_pos():
    env = make_env("1-1")
    env.reset()
    mismatches = 0
    n_checked = 0
    for _ in range(150):
        obs, reward, done, info = env.step(1)  # right+B
        ram = env.unwrapped.ram
        y_pixel = int(ram[ADDR_MARIO_Y])
        computed = 255 - y_pixel  # gym_super_mario_bros's own formula, normal (non-hole) case
        n_checked += 1
        if computed != info["y_pos"]:
            mismatches += 1
        if done:
            break
    env.close()
    assert n_checked > 0
    assert mismatches == 0, f"{mismatches}/{n_checked} frames disagreed with gym's own info['y_pos']"


def test_addr_mario_y_is_not_the_old_viewport_flag():
    """The bug this fix corrects: the old address (0x00B5) stayed
    constant at 1 across an entire run, including jumps -- the new one
    must not. Uses "right + A" (jump held) throughout, not a plain walk
    -- Mario's real Y genuinely doesn't vary while only ever walking on
    flat ground, so a plain walk can't tell the fix apart from the bug."""
    env = make_env("1-1")
    env.reset()
    values_seen = set()
    for _ in range(150):
        obs, reward, done, info = env.step(2)  # ["right", "A"] -- jump held
        values_seen.add(int(env.unwrapped.ram[ADDR_MARIO_Y]))
        if done:
            break
    env.close()
    assert len(values_seen) > 1, "ADDR_MARIO_Y stayed constant -- this is the old viewport-flag bug"
