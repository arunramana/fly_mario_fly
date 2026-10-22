"""Decode one SMB1 area-object stream (L_* in the community disassembly "smbdis.asm") into features and a tile map.

Format (AreaParserCore / ProcessAreaData / DecodeAreaData in the disassembly):
  header, 2 bytes   b0 = TT EEE SSS (timer code, player entrance control, foreground scenery / bg colour)
                    b1 = SS BB TTTT (area style, background scenery, terrain control)
  object, 2 bytes   b0 = XXXX RRRR (column inside the page, row), b1 = P III LLLL (new-page flag, object id, length);
                    ends at $FD.  Rows 0-11 are normal objects (id 0 = small objects picked by the low nibble),
                    row 12 / 15 = special objects, row 13 = page control / special objects, row 14 = terrain change.
The renderer draws the tile map column by column: scenery, then the terrain bits for the current terrain control, then
the objects covering that column; this module replays that to get the exact metatile of every cell. A change of terrain
control takes effect from the column after the object (the renderer draws terrain before it runs that column's objects).
Rows are tile rows 0-12 (row 11 is the first ground row); y in the output is row * 16 in tile-buffer coordinates.
"""
from __future__ import annotations

from fly_mario.mario.leveldata import rom as R

# ---- tables copied from the disassembly -------------------------------------------------------------------------------
TERRAIN_BITS = ((0x00, 0x00), (0x00, 0x18), (0x01, 0x18), (0x07, 0x18), (0x0F, 0x18), (0xFF, 0x18), (0x01, 0x1F),
                (0x07, 0x1F), (0x0F, 0x1F), (0x81, 0x1F), (0x01, 0x00), (0x8F, 0x1F), (0xF1, 0x1F), (0xF9, 0x18),
                (0xF1, 0x18), (0xFF, 0x1F))            # TerrainRenderBits: byte 0 = rows 0-7, byte 1 = rows 8-12 (bit 0 = first row)
TERRAIN_TILE = (0x69, 0x54, 0x52, 0x62)                # TerrainMetatiles by area type
SOLID_TILE = (0x69, 0x61, 0x61, 0x62)                  # SolidBlockMetatiles
BRICK_TILE = (0x22, 0x51, 0x52, 0x52, 0x88)            # BrickMetatiles (4 = cloud)
COIN_TILE = (0xC3, 0xC2, 0xC2, 0xC2)
HOLE_TILE = (0x87, 0, 0, 0)
BRICK_Q_TILES = (0xC1, 0xC0, 0x5F, 0x60, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E)
VERT_PIPE = (0x11, 0x10, 0x15, 0x14, 0x13, 0x12, 0x15, 0x14)
STAIR_ROW = (3, 3, 4, 5, 6, 7, 8, 9, 10)
STAIR_HEIGHT = (7, 7, 6, 5, 4, 3, 2, 1, 0)
SIDE_SHAFT = (0x15, 0x14, 0, 0)
SIDE_TOP = (0x15, 0x1E, 0x1D, 0x1C)
SIDE_BOTTOM = (0x15, 0x21, 0x20, 0x1F)
CASTLE = ((0, 0x45, 0x45, 0x45, 0), (0, 0x48, 0x47, 0x46, 0), (0x45, 0x49, 0x49, 0x49, 0x45), (0x47, 0x47, 0x4A, 0x47, 0x47),
          (0x47, 0x47, 0x4B, 0x47, 0x47), (0x49, 0x49, 0x49, 0x49, 0x49), (0x47, 0x4A, 0x47, 0x4A, 0x47),
          (0x47, 0x4B, 0x47, 0x4B, 0x47), (0x47, 0x47, 0x47, 0x47, 0x47), (0x4A, 0x47, 0x4A, 0x47, 0x4A), (0x4B, 0x47, 0x4B, 0x47, 0x4B))
FORE_SCENERY = ((0x86, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x87, 0x69, 0x69),     # in water
                (0, 0, 0, 0, 0, 0x45, 0x47, 0x47, 0x47, 0x47, 0x47, 0, 0),                          # wall
                (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x86, 0x87))                                      # over water
LOW_BOUNDS = (0x10, 0x51, 0x88, 0xC0)                  # BlockBuffLowBounds: a metatile below its group's bound is not stored
PLAYER_START_Y = (0x00, 0x20, 0xB0, 0x50, 0x00, 0x00, 0xB0, 0xB0, 0xF0)    # PlayerStarting_Y_Pos by entrance control
TIMER = (None, 400, 300, 200)                          # GameTimerData[GameTimerSetting]; 0 = keep the running timer
STYLES = ("treetop", "mushroom", "cannon")             # AreaStyle 0, 1, 2 (3 = cloud override, drawn like treetops)
WARP_WORLDS = {4: (4, 3, 2), 5: (5,), 6: (8, 7, 6)}    # WarpZoneNumbers by WarpZoneControl

SMALL = {0: ("question", "power-up", False), 1: ("question", "coin", False), 2: ("hidden", "coin", True),
         3: ("hidden", "1-up", True), 4: ("brick", "power-up", False), 5: ("brick", "vine", False),
         6: ("brick", "star", False), 7: ("brick", "multi-coin", False), 8: ("brick", "1-up", False)}
LARGE = ("pipe_warp", "ledge", "brick_row", "solid_row", "coin_row", "brick_column", "solid_column", "pipe")
ROW12 = ("hole", "pulley_rope", "bridge_high", "bridge_middle", "bridge_low", "hole_water", "question_row_high",
         "question_row_low")
ROW15 = ("endless_rope", "balance_rope", "castle", "staircase", "exit_pipe", "flag_balls")
ROW13 = ("intro_pipe", "flagpole", "axe", "chain", "castle_bridge", "scroll_lock_warp", "scroll_lock", "scroll_lock",
         "frenzy_flying_cheep", "frenzy_bullet_or_cheep", "frenzy_stop", "loop_command")


class Obj:
    __slots__ = ("col", "row", "id", "kind", "len", "b1", "page", "x", "attrs")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def solid_bits(tile: int) -> bool:
    return tile >= LOW_BOUNDS[tile >> 6]


# ---- 1. read the byte stream ------------------------------------------------------------------------------------------
def read_header(rom: R.Rom, cpu: int) -> dict:
    b0, b1 = rom.byte(cpu), rom.byte(cpu + 1)
    fore = b0 & 7
    style = b1 >> 6
    return {"timer_code": b0 >> 6, "entrance_ctrl": (b0 >> 3) & 7, "foreground": fore if fore < 4 else 0,
            "bg_color": fore if fore >= 4 else 0, "terrain": b1 & 15, "bg_scenery": (b1 >> 4) & 3,
            "style": 0 if style == 3 else style, "cloud": style == 3}


def read_objects(rom: R.Rom, cpu: int) -> list:
    """Replays the page logic of ProcessAreaData: bit 7 of byte 2 = next page, row 13 without bit 6 = jump to a page."""
    pos, page, out = cpu + 2, 0, []
    while rom.byte(pos) != 0xFD:
        b0, b1 = rom.byte(pos), rom.byte(pos + 1)
        pos += 2
        sel = bool(b1 & 0x80)
        if sel:
            page += 1
        row = b0 & 15
        if row == 13 and not (b1 & 0x40):
            if not sel:
                page = b1 & 0x1F
            continue
        col = page * 16 + (b0 >> 4)
        if row == 14:
            kind, oid, length = "terrain_change", None, b1 & 15
        elif row == 13:
            oid = b1 & 0x3F
            kind, length = ROW13[oid] if oid < len(ROW13) else f"row13_{oid}", 0
        elif row == 12:
            oid = (b1 >> 4) & 7
            kind, length = ROW12[oid], b1 & 15
        elif row == 15:
            oid = (b1 >> 4) & 7
            kind, length = (ROW15[oid] if oid < len(ROW15) else f"row15_{oid}"), b1 & 15
        elif b1 & 0x70:
            oid = (b1 >> 4) & 7
            if oid == 7 and (b1 & 8):
                oid = 0                                  # DecodeAreaData: pipe id 7 + d3 = the pipes that lead somewhere
            kind, length = LARGE[oid], b1 & 15
        else:
            oid = b1 & 15
            kind, length = (f"small_{oid}"), 0
        out.append(Obj(col=col, row=row, id=oid, kind=kind, len=length, b1=b1, page=page, x=col * 16))
    return out


# ---- 2. replay the renderer column by column ---------------------------------------------------------------------------
def _put(buf: list, row: int, tile: int, height: int) -> None:
    """RenderUnderPart: draw `tile` down `height + 1` rows from `row`, keeping some tiles already there."""
    y = height
    while row < 13:
        cur = buf[row]
        if cur == 0 or cur == 0xC0:
            buf[row] = tile
        elif cur in (0x17, 0x1A) or cur > 0xC0:
            pass
        elif cur != 0x54 or tile != 0x50:
            buf[row] = tile
        row += 1
        y = (y - 1) & 0xFF
        if y & 0x80 or row >= 13:
            break


def _column_writes(o: Obj, area_type: int, header: dict, first_col: bool) -> dict:
    """{column offset: [(row, tile, height, direct)]} the object draws; `direct` skips the keep rules."""
    k, r, n, w = o.kind, o.row, o.len, {}

    def add(c, row, tile, h=0, direct=False):
        w.setdefault(c, []).append((row, tile, h, direct))

    if k in ("brick_row", "solid_row", "coin_row"):
        cloud = header["cloud"] and k == "brick_row"
        tile = {"brick_row": BRICK_TILE[4 if cloud else area_type], "solid_row": SOLID_TILE[area_type],
                "coin_row": COIN_TILE[area_type]}[k]
        for c in range(n + 1):
            add(c, r, tile)
    elif k in ("brick_column", "solid_column"):
        add(0, r, (BRICK_TILE if k == "brick_column" else SOLID_TILE)[area_type], n)
    elif k in ("pipe", "pipe_warp"):
        lead, height = k == "pipe_warp", o.b1 & 7
        for c in range(2):
            y = 1 - c + (0 if lead else 4)
            add(c, r, VERT_PIPE[y], 0)
            add(c, r + 1, VERT_PIPE[y + 2], height - 1)
    elif k == "ledge":
        style = header["style"]
        if style == 2:                                   # bullet bill cannon column
            add(0, r, 0x64, 0)
            if n >= 1:
                add(0, r + 1, 0x65, 0)
            if n >= 2:
                add(0, r + 2, 0x66, n - 2)
        elif style == 1:                                 # mushroom platform
            half = n >> 1
            for c in range(n + 1):
                if c == 0:
                    add(c, r, 0x19, 0)
                elif c == n:
                    add(c, r, 0x1B, 0)
                else:
                    add(c, r, 0x1A, 0)
                    if n - c == half:
                        add(c, r + 1, 0x4F, 0, True)
                        add(c, r + 2, 0x50, 0x0F)
        else:                                            # treetop (also the cloud-type platforms)
            for c in range(n + 1):
                if c == n and n > 0:
                    add(c, r, 0x18, 0)
                elif c == 0 and o.col != 0:
                    add(c, r, 0x16, 0)
                else:
                    add(c, r, 0x17, 0, True)
                    add(c, r + 1, 0x4C, 0x0F)
    elif k == "hole":
        for c in range(n + 1):
            add(c, 8, HOLE_TILE[area_type], 0x0F)
    elif k == "hole_water":
        for c in range(n + 1):
            add(c, 10, 0x86, 0, True)
            add(c, 11, 0x87, 1)
    elif k in ("bridge_high", "bridge_middle", "bridge_low"):
        top = {"bridge_high": 6, "bridge_middle": 7, "bridge_low": 9}[k]
        for c in range(n + 1):
            add(c, top, 0x0B, 0, True)
            add(c, top + 1, 0x63, 0)
    elif k == "pulley_rope":
        for c in range(n + 1):
            add(c, 0, 0x42 if c == 0 else (0x43 if c == n else 0x41), 0, True)
    elif k in ("question_row_high", "question_row_low"):
        for c in range(n + 1):
            add(c, 3 if k == "question_row_high" else 7, 0xC0, 0, True)
    elif k == "staircase":
        for c in range(n + 1):
            y = 8 - c
            if y >= 0:
                add(c, STAIR_ROW[y], 0x61, STAIR_HEIGHT[y])
            else:
                add(c, STAIR_ROW[0], 0x61, STAIR_HEIGHT[0])
    elif k == "castle":
        for c in range(5):
            ln, rr = 4 - c, r
            for i in range(11):
                if rr >= 11:
                    break
                add(c, rr, CASTLE[i][ln], 0, True)
                rr += 1
            if (o.col + c) >> 4 and (ln == 1 or (r == 0 and ln == 3)):
                add(c, 10, 0x52, 0, True)                # PlayerStop: the brick that stops Mario at the end of the level
    elif k in ("exit_pipe", "intro_pipe"):
        nyb = n if k == "exit_pipe" else 0x0A
        for c in range(4):
            y = 3 - c
            shaft = nyb - 2
            if SIDE_SHAFT[y]:
                add(c, 0, SIDE_SHAFT[y], shaft)
            add(c, shaft + 1, SIDE_TOP[y], 0, True)
            add(c, shaft + 2, SIDE_BOTTOM[y], 0, True)
    elif k == "flagpole":
        add(0, 0, 0x24, 0, True)
        add(0, 1, 0x25, 8)
        add(0, 10, 0x61, 0, True)
    elif k == "axe":
        add(0, 6, 0xC5, 0)
    elif k == "chain":
        add(0, 7, 0x0C, 0)
    elif k == "castle_bridge":
        for c in range(13):
            add(c, 8, 0x89, 0)
    elif k == "endless_rope":
        add(0, 0, 0x40, 0x0F)
    elif k == "balance_rope":
        add(0, 1, 0x44, 0x0F)
        add(0, 1, 0x40, n)
    elif k == "flag_balls":
        add(0, 2, 0x6D, n)
    elif k.startswith("small_"):
        i = o.id
        if i <= 3:
            add(0, r, BRICK_Q_TILES[i], 0)
        elif i <= 8:
            add(0, r, BRICK_Q_TILES[i + (0 if area_type == 1 else 5)], 0)
        elif i == 9:
            add(0, r, 0x6B, 0, True)
            add(0, r + 1, 0x6C, 0, True)
        elif i == 10:
            add(0, r, 0xC4, 0)
        elif i == 11:
            add(0, r, 0x67, 0, True)
            add(0, r + 1, 0x68, 0, True)
    return w


def render(header: dict, objs: list, area_type: int, ncols: int, world8: bool = False) -> list:
    """The tile id of every cell: a list of `ncols` columns of 13 rows."""
    changes = []                                         # (first column the new value applies to, terrain, foreground)
    writes: dict = {}
    # ProcessAreaData runs the three object slots 2, 1, 0 once per column: a slot holding an object with a length draws its next
    # column, an empty slot loads the next stream object if it starts in this column. So continuing objects and new ones are
    # drawn in slot order, not in file order (matters where they overlap, e.g. a brick row across a hole).
    slots: list = [None, None, None]                     # each [column writes {offset: [...]}, offset of the next column, last offset]
    ptr = 0
    for col in range(ncols):
        while ptr < len(objs) and objs[ptr].col < col:
            ptr += 1                                     # behind the renderer: never loaded
        for x in (2, 1, 0):
            if slots[x] is not None:
                parts, k, last = slots[x]
                writes.setdefault(col, []).extend(parts.get(k, ()))
                slots[x] = None if k >= last else [parts, k + 1, last]
            elif ptr < len(objs) and objs[ptr].col == col:
                o = objs[ptr]
                ptr += 1
                if o.kind == "terrain_change":
                    if o.b1 & 0x40:
                        f = o.b1 & 7
                        changes.append((col + 1, "fore", f if f < 4 else 0))
                    else:
                        changes.append((col + 1, "terrain", o.b1 & 15))
                    continue
                parts = _column_writes(o, area_type, header, False)
                writes.setdefault(col, []).extend(parts.get(0, ()))
                last = max(parts) if parts else 0
                if last > 0:
                    slots[x] = [parts, 1, last]
    terrain, fore, ci = header["terrain"], header["foreground"], 0
    changes.sort(key=lambda t: t[0])
    cols = []
    for col in range(ncols):
        while ci < len(changes) and changes[ci][0] <= col:
            if changes[ci][1] == "terrain":
                terrain = changes[ci][2]
            else:
                fore = changes[ci][2]
            ci += 1
        buf = [0] * 13
        if fore:
            for i, t in enumerate(FORE_SCENERY[fore - 1]):
                if t:
                    buf[i] = t
        base = 0x62 if (area_type == 0 and world8) else TERRAIN_TILE[area_type]
        if header["cloud"]:
            base = 0x88
        tile = base
        bits = list(TERRAIN_BITS[terrain])
        for bi in range(2):
            byte = bits[bi] & 8 if (header["cloud"] and bi == 1) else bits[bi]
            for b in range(8 if bi == 0 else 5):
                row = bi * 8 + b
                if byte & (1 << b):
                    buf[row] = tile
                if area_type == 2 and row == 10:
                    tile = 0x54
        for row, t, h, direct in writes.get(col, ()):
            if direct:
                if row < 13:
                    buf[row] = t
            else:
                _put(buf, row, t, h)
        cols.append(buf)
    return cols
