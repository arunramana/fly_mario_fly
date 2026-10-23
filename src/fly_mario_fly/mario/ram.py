"""Raw RAM readers shared by the objects and scenes. Addresses and sizes come from facts, never from here."""
from __future__ import annotations

from fly_mario_fly.contracts import Box, MarioState, ObjectInstance


def mario_x(ram, facts) -> int:
    r = facts["ram"]
    return int(ram[r["mario_page"]]) * 256 + int(ram[r["mario_x"]])


def mario_box_size(ram, facts) -> tuple:
    """(w, h): a big or fire Mario is taller; his feet stay the reference."""
    m = facts["mario"]
    big = int(ram[facts["ram"]["power"]]) >= 1
    return tuple(m["box_big"] if big else m["box_small"])


def read_mario(ram, facts) -> MarioState:
    r, m = facts["ram"], facts["mario"]
    w, h = mario_box_size(ram, facts)
    feet = int(ram[r["mario_feet_y"]])
    power = min(int(ram[r["power"]]), len(m["power_names"]) - 1)
    return MarioState(x=float(mario_x(ram, facts)), y=float(feet - h), w=float(w), h=float(h),
                      airborne=int(ram[r["player_state"]]) != 0, power=m["power_names"][power],
                      facing=-1 if int(ram[r["facing"]]) == 2 else 1)


def side_of(box: Box, ram, facts) -> str:
    """Where a box sits relative to Mario's box: above / below when they overlap in x, else ahead / behind."""
    mario = read_mario(ram, facts)
    x_overlap = mario.x < box.x + box.w and mario.x + mario.w > box.x
    if x_overlap:
        if box.y + box.h <= mario.y:
            return "above"
        if box.y >= mario.y + mario.h:
            return "below"
        return "ahead"
    return "ahead" if box.x >= mario.x else "behind"


def instance(kind: str, ident: int, box: Box, ram, facts, **state) -> ObjectInstance:
    return ObjectInstance(kind, ident, box, side_of(box, ram, facts), state)


# ---- enemy slots -----------------------------------------------------------

def active_slots(ram, facts) -> list:
    """[(slot, type byte, ram state, world x, y byte)] for every active enemy slot (0-4)."""
    r, g = facts["ram"], facts["grid"]
    return [(s, int(ram[r["enemy_type"] + s]), int(ram[r["enemy_state"] + s]),
             int(ram[r["enemy_page"] + s]) * 256 + int(ram[r["enemy_x"] + s]), int(ram[r["enemy_y"] + s]))
            for s in range(g["enemy_slots"]) if int(ram[r["enemy_active"] + s])]


def remove_types(env, facts, type_bytes) -> None:
    """Switch off every active enemy slot (0-4) whose type byte is in `type_bytes`."""
    types = set(type_bytes)
    _switch_off(env, facts, lambda typ: typ in types)


def sweep_enemies(env, facts, keep_types=()) -> None:
    """Switch off every active enemy slot (0-4), whatever its type, except the type bytes in `keep_types`."""
    keep = set(keep_types)
    _switch_off(env, facts, lambda typ: typ not in keep)


def _switch_off(env, facts, wanted) -> None:
    r, g = facts["ram"], facts["grid"]
    for s in range(g["enemy_slots"]):
        if int(env.ram[r["enemy_active"] + s]) and wanted(int(env.ram[r["enemy_type"] + s])):
            env.poke(r["enemy_active"] + s, 0)


# ---- tile buffer -------------------------------------------------------------

def tile(ram, facts, wx: int, row: int) -> int:
    g = facts["grid"]
    page, col = wx // 256, (wx % 256) // g["tile"]
    return int(ram[facts["ram"]["tile_buffer"] + g["page_bytes"] * (page % 2) + 16 * row + col])


def visible_columns(ram, facts):
    """World x of each 16-px column on the visible screen (the buffer holds only what has scrolled in)."""
    r, g = facts["ram"], facts["grid"]
    left = int(ram[r["screen_page"]]) * 256 + int(ram[r["screen_x"]])
    t = g["tile"]
    return range((left // t) * t, left + g["screen_w"], t)


def merged_faces(ram, facts, ids) -> list:
    """Raw wall faces made of tiles in `ids` standing on the ground: [(x0, x1, H)].

    Per column, H = stack height (px) of those tiles upward from the stand row; neighbouring columns of
    equal height are one face (a pipe is two columns wide)."""
    g = facts["grid"]
    t, stand = g["tile"], g["stand_row"]
    ids = set(ids)
    out = []
    for wx in visible_columns(ram, facts):
        if tile(ram, facts, wx, stand) not in ids:
            continue
        r = stand
        while r >= 0 and tile(ram, facts, wx, r) in ids:
            r -= 1
        H = (stand - r) * t
        if out and out[-1][1] == wx and out[-1][2] == H:
            out[-1] = (out[-1][0], wx + t, H)
        else:
            out.append((wx, wx + t, H))
    return out


def face_box(x0: int, x1: int, H: int, facts) -> Box:
    g = facts["grid"]
    return Box(x0, g["ground_row"] * g["tile"] - H, x1 - x0, H)


def tile_boxes(ram, facts, ids) -> list:
    """[(x, row, tile id)] for every visible tile above the ground whose id is in `ids`."""
    g = facts["grid"]
    ids = set(ids)
    return [(wx, r, tile(ram, facts, wx, r)) for wx in visible_columns(ram, facts)
            for r in range(g["ground_row"]) if tile(ram, facts, wx, r) in ids]


# ---- support: what Mario can stand on (the pit rule) ---------------------------------------------------------------

def is_solid(facts, tile_id: int) -> bool:
    """Does this metatile stop Mario? The game's own rule, from facts["collision"]: non-zero and below its group's upper extent."""
    c = facts["collision"]
    t = int(tile_id)
    return t != c["empty"] and t < c["stop_upper_ext"][t >> 6] and t not in c["not_solid"]


def takeoff_ground(ram, facts) -> int:
    """Feet y of the ground Mario is walking on, or took off from: his feet on the ground, else where the jump began."""
    r = facts["ram"]
    if int(ram[r["player_state"]]) == 0:
        return int(ram[r["mario_feet_y"]])
    origin = int(ram[r["jump_origin_y"]])
    return origin if origin else facts["grid"]["ground_row"] * facts["grid"]["tile"]


def support_top(ram, facts, wx: int, ground: int):
    """y of the top of what a column offers Mario: the first solid tile at or below the `ground` row, then up through the
    solid stack that sits on it (a pipe or stair column beside the floor). None when the column has nothing to stand on."""
    g = facts["grid"]
    t, last = g["tile"], g["ground_row"] + 1
    row = max(0, min(int(ground) // t, last))
    while row <= last and not is_solid(facts, tile(ram, facts, wx, row)):
        row += 1
    if row > last:
        return None
    while row > 0 and is_solid(facts, tile(ram, facts, wx, row - 1)):
        row -= 1
    return row * t
