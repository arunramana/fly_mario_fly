# What this file does, in plain English:
# Answers "what is on the screen?" from the game's memory: where the screen's left edge is in
# the level, where an enemy is actually drawn, and whether it is inside the picture. A fly's
# eye only sees the picture, so the honest-senses mode uses this to ignore everything else.
"""mario/ram/screen.py -- drawn (camera-relative) positions. Verified against the emulator in
docs/AUDIT_biological_validity.md: Mario's drawn x (RAM 0x03AD) == absolute x - ScreenLeft for every frame of a
1895-frame replay."""

from __future__ import annotations

from mario.ram.addresses import ADDR_ENEMY_PAGE, ADDR_ENEMY_X

ADDR_SCREEN_LEFT_PAGE = 0x071A
ADDR_SCREEN_LEFT_X = 0x071C
SCREEN_WIDTH_PX = 256
SCREEN_COLS = 16


def screen_left(ram) -> int:
    """The level x (px) of the screen's left edge."""
    return int(ram[ADDR_SCREEN_LEFT_PAGE]) * 256 + int(ram[ADDR_SCREEN_LEFT_X])


def enemy_drawn_x(ram, slot: int) -> int:
    """Where enemy `slot` is drawn, in screen pixels (negative / >= 256 = outside the picture)."""
    return int(ram[ADDR_ENEMY_PAGE + slot]) * 256 + int(ram[ADDR_ENEMY_X + slot]) - screen_left(ram)


def enemy_on_screen(ram, slot: int, width_px: int = 16) -> bool:
    """True while any part of the enemy is inside the picture."""
    x = enemy_drawn_x(ram, slot)
    return -width_px < x < SCREEN_WIDTH_PX


def mario_drawn_col(ram) -> int:
    """The tile column (0-15) Mario is drawn in (RAM 0x03AD is his drawn x)."""
    return int(ram[0x03AD]) // 16
