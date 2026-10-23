"""Decode one SMB1 enemy-object stream (E_* in the community disassembly "smbdis.asm": ProcessEnemyData, ParseRow0e,
HandleGroupEnemies, the Init* routines).

Format: 2-byte entries  b0 = XXXX RRRR (column inside the page, row), b1 = P H IIIIII (new-page flag, hard-mode-only
flag, enemy id); row 15 = page jump (b1 = page); row 14 = 3 bytes, a link to another area (b1 = area pointer, byte 3 =
world<<5 | entrance page); $FF ends the stream. Enemy ids $37-$3E are groups of 2 or 3 goombas / koopas spawned at the
right screen edge. All positions are world pixels; `row` * 16 is the tile-buffer y (ground = row 11).
"""
from __future__ import annotations

from fly_mario_fly.mario.leveldata import rom as R

NAMES = {
    0x00: "green_koopa", 0x02: "buzzy_beetle", 0x03: "red_koopa", 0x05: "hammer_bro", 0x06: "goomba", 0x07: "blooper",
    0x08: "bullet_bill", 0x0A: "grey_cheep_cheep", 0x0B: "red_cheep_cheep", 0x0C: "podoboo", 0x0D: "piranha_plant",
    0x0E: "green_paratroopa_jumping", 0x0F: "red_paratroopa", 0x10: "green_paratroopa_flying", 0x11: "lakitu",
    0x12: "spiny_thrower", 0x14: "flying_cheep_cheep_frenzy", 0x15: "bowser_flame", 0x16: "fireworks",
    0x17: "bullet_bill_frenzy", 0x18: "frenzy_stop",
    0x1B: "firebar", 0x1C: "firebar", 0x1D: "firebar", 0x1E: "firebar", 0x1F: "long_firebar",
    0x24: "balance_lift", 0x25: "vertical_platform", 0x26: "large_lift_up", 0x27: "large_lift_down",
    0x28: "horizontal_platform", 0x29: "falling_platform", 0x2A: "ride_right_platform", 0x2B: "small_lift_up",
    0x2C: "small_lift_down", 0x2D: "bowser", 0x2E: "power_up", 0x2F: "vine", 0x32: "jumpspring", 0x35: "toad",
}
GROUP_IDS = range(0x37, 0x3F)
PLATFORMS = range(0x24, 0x2D)
FIREBARS = range(0x1B, 0x20)
FRENZY = (0x12, 0x14, 0x17, 0x18, 0x15, 0x16)
FIREBAR_SPEED = {0x1B: ("slow", "clockwise"), 0x1C: ("fast", "clockwise"), 0x1D: ("slow", "counter-clockwise"),
                 0x1E: ("fast", "counter-clockwise"), 0x1F: ("slow", "clockwise")}      # FirebarSpinSpdData / FirebarSpinDirData
PLATFORM_SIZE = {i: ("small" if i in (0x2B, 0x2C) else "large") for i in PLATFORMS}


def read(rom: R.Rom, cpu: int) -> tuple:
    """(entries, links) of one enemy stream, in file order."""
    pos, page, sel = cpu, 0, False
    entries, links = [], []
    edge = 255                   # the screen's right edge as it scrolls: an entry is only looked at once the one before it is done
    while rom.byte(pos) != 0xFF:
        b0, b1 = rom.byte(pos), rom.byte(pos + 1)
        if b1 & 0x80 and not sel:
            sel = True
            page += 1
        row = b0 & 15
        if row == 15 and not sel:
            page, sel, pos = b1 & 0x3F, True, pos + 2
            continue
        x = page * 256 + (b0 & 0xF0)
        if row == 14:
            third = rom.byte(pos + 2)
            links.append({"x": x, "pointer": b1, "world": (third >> 5) + 1, "entrance_page": third & 0x1F})
            pos += 3
            edge = max(edge, x - 48)
        else:
            entry = {"x": x, "row": row, "id": b1 & 0x3F, "hard_only": bool(b1 & 0x40)}
            if x < edge:         # PositionEnemyObj: an entry already left of the right edge when it is reached is skipped
                entry["never_spawns"] = True
            else:
                edge = max(edge, x - 48)         # spawned (or skipped as hard-mode only) once the right edge + 48 reaches x
            entries.append(entry)
            pos += 2
        sel = False
    return entries, links


def expand(e: dict) -> list:
    """One entry -> the things it makes: [{type, group, ...}] with ram_y = the byte the game holds in Enemy_Y_Position."""
    i, x, row = e["id"], e["x"], e["row"]
    base = {"hard_only": e["hard_only"], **({"never_spawns": True} if e.get("never_spawns") else {})}
    if i in GROUP_IDS:                                   # HandleGroupEnemies: 2-3 enemies, 24 px apart, at the screen's right edge
        n = 3 if (i - 0x37) & 1 else 2
        kind = "goomba" if i - 0x37 < 4 else "green_koopa"
        top = 0x70 if (i - 0x37) & 2 else 0xB0
        return [{**base, "type": kind, "id": 0x06 if kind == "goomba" else 0x00, "x": x - 40 + 24 * k, "row": top // 16,
                 "y": top, "ram_y": top + 8, "group": n, "approx_x": True} for k in range(n)]
    ram_y = (row * 16 + (8 if i < 0x15 else 0)) & 0xFF
    out = {**base, "type": NAMES.get(i, f"unknown_{i:#04x}"), "id": i, "x": x, "row": row, "y": row * 16, "ram_y": ram_y}
    if i == 0x0C:                                        # InitPodoboo: starts below the screen and jumps up from its column
        out["ram_y"] = 2
    if i == 0x1F:                                        # DuplicateEnemyObj: a second bar is made at the same spot
        out["two_bars"] = True
    if i in FIREBARS:
        out["speed"], out["direction"] = FIREBAR_SPEED[i]
        out["ram_x"], out["ram_y"] = x + 4, row * 16 + 4
    if i in PLATFORMS:
        out["size"] = PLATFORM_SIZE[i]
        if i == 0x25:                                    # InitVertPlatform: top and centre y it oscillates around
            top, centre = (ram_y, (ram_y + 0x40) & 0xFF) if ram_y < 0x80 else ((-ram_y) & 0xFF, (ram_y + 0xC0) & 0xFF)
            out["y_top"], out["y_centre"] = top, centre
    return [out]
