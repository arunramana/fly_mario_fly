"""Build the level database: decode every area block of the ROM and tie them to the 32 stages.

areas  = one entry per ROM area block (a block is shared by stages that reuse it, e.g. 1-3 and 5-3)
stages = the 32 stages: which blocks they use (main / intro / sub-areas reached by pipes and vines), flag x, time limit
envs   = the 3 whole-game envs
See tools/read_rom_levels.py (writes facts/level_db.json) and leveldata/__init__.py (reads it).
"""
from __future__ import annotations

from fly_mario_fly.mario.leveldata import areas as A, enemies as E, rom as R

VERSION = 1
NOTES = {
    "hidden_1up": "A hidden 1-up block (only_if hidden_1up_flag) is drawn only while the game's Hidden1UpFlag is set: it is set at power-on "
                  "and after a life is lost, and cleared once one such block has been drawn. A fresh game meets it in 1-1.",
    "hard_only": "Entries with hard_only appear only in secondary hard mode: stages 5-3 and later.",
    "never_spawns": "The enemy stream is read in order: an entry already left of the screen's right edge when it is reached is skipped "
                    "(the game's PositionEnemyObj). Those entries are marked never_spawns.",
    "group": "Enemy ids $37-$3E make 2-3 goombas / koopas 24 px apart at the screen's right edge when the entry is reached: x is "
             "approximate (approx_x), y is exact.",
    "from_pipe": "Every pipe (decorative or not) spawns a piranha plant when its column is drawn, except in 1-1 (no_pipe_piranha). "
                 "ram_y is the pipe top in screen y.",
    "frenzy": "Entries that start a stream of cheep-cheeps / bullet bills / lakitu spinies are in `frenzy` (and `frenzies` for the "
              "area-object ones); the flying things they make are not listed.",
    "flag_get_x": "Mario's x when the game reports flag_get: measured 7 px left of the flagpole x, 7 px right of the axe x.",
    "windows": "Each stage area has a window [x0, x1): the part a visit can meet (the pipe-intro screen: none; a sub-area: from the "
               "entrance page; the shared bonus-room block: its one 512 px room). stage.summary is computed over the windows.",
}
NOTE_POWER_UP = ('"power-up" blocks hold a mushroom or a fire flower: the game picks at run time, a mushroom when Mario is '
                 'small, a fire flower when he is big or fire. The ROM data does not say which.')
HARD_FROM = (5, 3)                         # secondary hard mode (objects flagged hard_only appear) from stage 5-3 on
INTRO_WORLDS = (1, 2, 4, 7)                # worlds with 5 area slots: slot 1 is the pipe-intro screen before stage 2
TILE = 16
FLAG_GET_DX, AXE_GET_DX = 7, 7           # measured on the emulator (tools/verify_rom_levels.py): Mario's x when flag_get fires is 7 px left of the
                                          # flagpole x and 7 px right of the axe x


# ---- one area block -------------------------------------------------------------------------------------------------
def _terrain_rows(control: int) -> dict:
    lo, hi = A.TERRAIN_BITS[control]
    rows = [r for r in range(13) if (lo | hi << 8) & (1 << r)]
    ceiling = [r for r in rows if r < 8]
    floor = [r for r in rows if r >= 8]
    return {"control": control, "ceiling_rows": ceiling, "floor_rows": floor}


def decode_area(rom: R.Rom, pointer: int) -> dict:
    typ, idx, ecpu, acpu = rom.locate(pointer)
    header = A.read_header(rom, acpu)
    objs = A.read_objects(rom, acpu)
    entries, links = E.read(rom, ecpu)
    kinds = {}
    feats: dict = {k: [] for k in ("pipes", "blocks", "bricks", "solid_blocks", "coins", "stairs", "ledges", "bridges",
                                   "cannons", "springs", "ropes", "exit_pipes", "scroll_locks", "frenzies", "decor")}
    flag = axe = castle = castle_bridge = intro_pipe = None
    loops, segs = [], [{"x": 0, **_terrain_rows(header["terrain"])}]
    extent = 0
    for o in objs:
        k, x, r, n = o.kind, o.x, o.row, o.len
        kinds[k] = kinds.get(k, 0) + 1
        width = (n + 1) * TILE
        if k in ("brick_row", "brick_column"):
            row = k == "brick_row"
            feats["bricks"].append({"x": x, "row": r, "w": n + 1 if row else 1, "h": 1 if row else n + 1})
            extent = max(extent, x + width)
        elif k in ("solid_row", "solid_column"):
            row = k == "solid_row"
            feats["solid_blocks"].append({"x": x, "row": r, "w": n + 1 if row else 1, "h": 1 if row else n + 1})
            extent = max(extent, x + width)
        elif k == "coin_row":
            feats["coins"].append({"x": x, "row": r, "w": n + 1})
        elif k in ("pipe", "pipe_warp"):
            h = 1 + max(1, o.b1 & 7)
            feats["pipes"].append({"x": x, "row": r, "y": r * TILE, "height": min(h, 11 - r), "w": 2,
                                   "enterable": k == "pipe_warp"})
        elif k == "ledge":
            if header["style"] == 2:
                feats["cannons"].append({"x": x, "row": r, "y": r * TILE, "height": n + 1})
            else:
                feats["ledges"].append({"x": x, "row": r, "w": n + 1, "style": "mushroom" if header["style"] == 1 else
                                        ("cloud" if header["cloud"] else "treetop")})
        elif k in ("bridge_high", "bridge_middle", "bridge_low"):
            top = {"bridge_high": 6, "bridge_middle": 7, "bridge_low": 9}[k]
            feats["bridges"].append({"x": x, "row": top + 1, "w": n + 1})
        elif k in ("question_row_high", "question_row_low"):
            row = 3 if k == "question_row_high" else 7
            for c in range(n + 1):
                feats["blocks"].append({"x": x + c * TILE, "row": row, "y": row * TILE, "block": "question",
                                        "contents": "coin", "hidden": False})
        elif k.startswith("small_"):
            i = o.id
            if i in A.SMALL:
                block, contents, hidden = A.SMALL[i]
                b = {"x": x, "row": r, "y": r * TILE, "block": block, "contents": contents, "hidden": hidden}
                if i == 3:
                    b["only_if"] = "hidden_1up_flag"     # Hidden1UpBlock is drawn only when that flag is set (collected a 1-up, ...)
                feats["blocks"].append(b)
            elif i == 9:
                feats["decor"].append({"x": x, "row": r, "what": "water_pipe"})
            elif i == 10:
                feats["blocks"].append({"x": x, "row": r, "y": r * TILE, "block": "empty", "contents": "none", "hidden": False})
            elif i == 11:
                feats["springs"].append({"x": x, "row": r, "y": r * TILE})
        elif k == "staircase":
            cols = [min(8 - c, 8) for c in range(n + 1)]
            feats["stairs"].append({"x": x, "columns": n + 1,
                                    "heights": [A.STAIR_HEIGHT[max(c, 0)] + 1 for c in cols]})
        elif k == "castle":
            castle = {"x": x, "row": r, "flag_star_x": x + 2 * TILE}
        elif k == "flagpole":
            flag = {"x": x}
        elif k == "axe":
            axe = {"x": x, "row": 6}
        elif k == "castle_bridge":
            castle_bridge = {"x": x, "w": 13 * TILE, "row": 8}
        elif k == "intro_pipe":
            intro_pipe = {"x": x}
        elif k == "exit_pipe":
            feats["exit_pipes"].append({"x": x, "row": n - 1, "w": 4})
        elif k in ("scroll_lock_warp", "scroll_lock"):
            feats["scroll_locks"].append({"x": x, "warp_zone": k == "scroll_lock_warp"})
        elif k in ("frenzy_flying_cheep", "frenzy_bullet_or_cheep", "frenzy_stop"):
            feats["frenzies"].append({"x": x, "kind": k.replace("frenzy_", "")})
        elif k in ("pulley_rope", "endless_rope", "balance_rope"):
            feats["ropes"].append({"x": x, "row": r, "kind": k, "w": n + 1 if k == "pulley_rope" else 1})
        elif k == "loop_command":
            loops.append(x)
        elif k == "terrain_change":
            if not (o.b1 & 0x40):
                segs.append({"x": x + TILE, **_terrain_rows(o.b1 & 15)})
    # ---- tiles
    end_marker = (flag or axe or castle_bridge or {}).get("x")
    all_x = [o.x for o in objs] + [e["x"] for e in entries]
    ncols = ((max(all_x + [0]) // 256) + 1) * 16 + 16
    cols = A.render(header, objs, typ, ncols, world8=False)
    width_px = end_marker + TILE if end_marker is not None else ((max(all_x + [extent - 1]) // 256) + 1) * 256
    end_col = min(ncols, width_px // TILE)
    masks = []
    for c in range(ncols):
        m = 0
        for r in range(13):
            if A.solid_bits(cols[c][r]):
                m |= 1 << r
        masks.append(m)
    tile_ids = sorted({cols[c][r] for c in range(end_col) for r in range(13) if A.solid_bits(cols[c][r])})
    floor = [bool(masks[c] & 0x1800) for c in range(ncols)]           # rows 11 and 12 (the ground rows)
    gaps, runs, c = [], [], 0
    while c < end_col:
        j = c
        while j < end_col and floor[j] == floor[c]:
            j += 1
        if floor[c]:
            runs.append({"x": c * TILE, "w": (j - c) * TILE})
        else:
            tile = cols[c][12]
            kind = "lava" if typ == 3 else ("water" if tile in (0x87,) or cols[c][11] == 0x87 else "pit")
            gaps.append({"x": c * TILE, "w": (j - c) * TILE, "kind": kind})
        c = j
    # ---- things that move
    enemies, platforms, firebars, frenzy_events = [], [], [], []
    for e in entries:
        for item in E.expand(e):
            i = item["id"]
            if i in E.PLATFORMS:
                platforms.append(item)
            elif i in E.FIREBARS:
                firebars.append(item)
            elif i in E.FRENZY:
                frenzy_events.append(item)
            else:
                enemies.append(item)
    for p in feats["pipes"]:                                          # VerticalPipe puts a piranha plant in every pipe (not in 1-1)
        enemies.append({"type": "piranha_plant", "id": 0x0D, "x": p["x"] + 8, "row": p["row"], "y": p["y"],
                        "ram_y": (p["y"] + 32) & 0xFF, "hard_only": False, "from_pipe": True})
    for lst in (enemies, platforms, firebars, frenzy_events):
        lst.sort(key=lambda d: (d["x"], d["row"]))
    pw = R.AREA_TYPES[typ]
    coverage = len([c for c in range(end_col) if floor[c]]) / max(end_col, 1)
    kind = "sky" if header["cloud"] else (pw if pw != "overground" else ("athletic" if coverage < 0.6 else "overground"))
    contents: dict = {}
    for b in feats["blocks"]:
        contents[b["contents"]] = contents.get(b["contents"], 0) + 1
    return {
        "key": R.area_key(pointer), "pointer": pointer, "area_type": pw, "kind": kind,
        "rom": {"area_data_cpu": acpu, "enemy_data_cpu": ecpu},
        "header": {**header, "time_limit": A.TIMER[header["timer_code"]], "start_y": A.PLAYER_START_Y[header["entrance_ctrl"]]
                   if header["entrance_ctrl"] < len(A.PLAYER_START_Y) else None},
        "width": width_px, "flag": flag, "axe": axe, "castle": castle, "castle_bridge": castle_bridge,
        "intro_pipe": intro_pipe, "loop_commands": loops,
        "terrain": segs, "floor_coverage": round(coverage, 3), "ground_runs": runs, "gaps": gaps,
        **feats, "block_contents": contents,
        "enemies": enemies, "platforms": platforms, "firebars": firebars, "frenzy": frenzy_events,
        "links": links,
        "tile_ids": tile_ids, "_cols": cols[:end_col],
        "solid": "".join(f"{m:04x}" for m in masks[:end_col]),
    }


# ---- stages ----------------------------------------------------------------------------------------------------------
def stage_slots(world: int, stage: int) -> tuple:
    """(main area slot, intro slot or None) inside the world's AreaAddrOffsets row; world, stage are 0-based."""
    if (world + 1) in INTRO_WORLDS:
        return (0, None) if stage == 0 else ((2, 1) if stage == 1 else (stage + 1, None))
    return stage, None


def hard_mode(world: int, stage: int) -> bool:
    return (world + 1, stage + 1) >= HARD_FROM


def _window(area: dict, item: dict) -> list | None:
    """[x0, x1) of the area a stage meets: all of the main area; a sub-area from the page Mario enters on; one 512 px room of the
    bonus-room block (five rooms side by side, picked by the entrance page); None = the pipe-intro screen, not counted."""
    if item["role"] == "intro":
        return None
    if item["role"] == "main":
        return [0, area["width"]]
    x0 = item["entrance_page"] * 256
    if len(area["exit_pipes"]) > 1:
        x0 = x0 // 512 * 512
        return [x0, x0 + 512]
    return [x0, area["width"]]


def _summary(areas: dict, ar: list, hard: bool, no_pipe_piranha: bool) -> dict:
    """Object-level summary of a stage over its windows: solid tile ids, enemy ids / types that spawn, block contents, gaps."""
    tiles, ids, types, contents, gaps = set(), set(), set(), {}, 0
    for item in ar:
        win = item["window"]
        if win is None:
            continue
        a = areas[item["key"]]
        x0, x1 = win
        for col in a["_cols"][x0 // TILE:x1 // TILE]:
            tiles.update(t for t in col if A.solid_bits(t))
        for key in ("enemies", "platforms", "firebars", "frenzy"):
            for e in a[key]:
                if x0 <= e["x"] < x1 and not e.get("never_spawns") and (hard or not e["hard_only"]) \
                        and not (e.get("from_pipe") and no_pipe_piranha):
                    ids.add(e["id"])
                    types.add(e["type"])
        for b in a["blocks"]:
            if x0 <= b["x"] < x1:
                contents[b["contents"]] = contents.get(b["contents"], 0) + 1
        gaps += sum(1 for g in a["gaps"] if g["x"] < x1 and g["x"] + g["w"] > x0)
    return {"tile_ids": sorted(tiles), "enemy_ids": sorted(ids), "enemy_types": sorted(types),
            "block_contents": {k: contents[k] for k in sorted(contents)}, "gaps": gaps}


def _pipe_targets(areas: dict, ar: list, world: int) -> tuple:
    """(pipes, warps): where each enterable pipe of the stage leads. A pipe goes to the area of the latest link (enemy-stream row 14)
    the screen has passed by then (link x within 176 px ahead of the pipe); the pipes just before a warp-zone marker are the warp pipes
    and lead to the worlds of WarpZoneNumbers, left to right."""
    pipes, warps = [], []
    for item in ar:
        if item["role"] == "intro":
            continue
        a = areas[item["key"]]
        x0, x1 = item["window"]
        locks = [s for s in a["scroll_locks"] if s["warp_zone"] and x0 <= s["x"] < x1]
        warp_x = set()
        if locks:
            ws = A.WARP_WORLDS[4 if world == 1 else (6 if a["area_type"] == "overground" else 5)]
            near = sorted((p for p in a["pipes"] if p["enterable"] and locks[0]["x"] - 640 <= p["x"] < locks[0]["x"]),
                          key=lambda p: p["x"])[-len(ws):]
            warp_x = {p["x"] for p in near}
            warps += [{"area": a["key"], "x": p["x"], "row": p["row"], "to_world": wd} for p, wd in zip(near, ws)]
        links = [lk for lk in a["links"] if lk["world"] == world]
        for p in a["pipes"]:
            near = [lk for lk in links if lk["x"] <= p["x"] + 176]
            if p["enterable"] and p["x"] not in warp_x and near and x0 <= p["x"] < x1:
                pipes.append({"area": a["key"], "x": p["x"], "row": p["row"], "to": R.area_key(near[-1]["pointer"]),
                              "entrance_page": near[-1]["entrance_page"]})
    return pipes, warps


def build() -> dict:
    rom = R.load()
    areas: dict = {}
    stages: dict = {}

    def area(pointer: int) -> dict:
        key = R.area_key(pointer)
        if key not in areas:
            areas[key] = decode_area(rom, pointer)
            areas[key]["used_by"] = []
        return areas[key]

    for w in range(8):
        for s in range(4):
            sid = f"{w + 1}-{s + 1}"
            main_slot, intro_slot = stage_slots(w, s)
            main_p = rom.area_pointer(w, main_slot)
            listing = [(main_p, "main", None)]
            if intro_slot is not None:
                listing.insert(0, (rom.area_pointer(w, intro_slot), "intro", None))
            seen, queue, exits = {R.area_key(main_p)}, [(main_p, 0, True)], []
            while queue:      # sub-areas: the main area's links, then (from each sub-area) the first link after its entrance page
                src, ep, is_main = queue.pop(0)
                valid = [lk for lk in area(src)["links"] if lk["world"] == w + 1 and lk["x"] >= ep * 256]
                for lk in (valid if is_main else valid[:1]):
                    dst, key = lk["pointer"], R.area_key(lk["pointer"])
                    exits.append({"from": R.area_key(src), "x": lk["x"], "to": key, "entrance_page": lk["entrance_page"],
                                  "kind": "enter" if is_main else "return"})
                    if key not in seen:
                        seen.add(key)
                        queue.append((dst, lk["entrance_page"], False))
                        listing.append((dst, "sub", (R.area_key(src), lk["entrance_page"])))
            ar = []
            for p, role, via in listing:
                a = area(p)
                a["used_by"].append(sid)
                item = {"key": a["key"], "role": role}
                if via:
                    item["via"] = via[0]
                    item["entrance_page"] = via[1]
                ar.append(item)
            m = areas[R.area_key(main_p)]
            end = next(({"area": e["key"], "x": (e["flag"] or e["axe"])["x"], "kind": "flagpole" if e["flag"] else "axe"}
                        for e in (areas[x["key"]] for x in ar if x["role"] != "intro") if e["flag"] or e["axe"]), None)
            if end:
                for x in ar:
                    if x["key"] == end["area"] and x["role"] == "sub":
                        x["role"] = "end"
            for x in ar:                                   # the part of each area a visit can meet (intro screen: none)
                x["window"] = _window(areas[x["key"]], x)
            pipe_to, warp_to = _pipe_targets(areas, ar, w + 1)
            stages[sid] = {
                "id": sid, "world": w + 1, "stage": s + 1, "kind": m["kind"], "area_type": m["area_type"], "main": m["key"],
                "pipe_exits": pipe_to, "warp_pipes": warp_to,
                "areas": ar, "exits": exits, "width": end["x"] if end else m["width"], "main_width": m["width"], "end": end,
                "summary": _summary(areas, ar, hard_mode(w, s), (w, s) == (0, 0)),
                "flag_get_x": (end["x"] - FLAG_GET_DX if end["kind"] == "flagpole" else end["x"] + AXE_GET_DX) if end else None,
                "flag_x": end["x"] if end and end["kind"] == "flagpole" else None,
                "axe_x": end["x"] if end and end["kind"] == "axe" else None, "time_limit": m["header"]["time_limit"],
                "hard_mode": hard_mode(w, s), "no_pipe_piranha": (w, s) == (0, 0),
                "warp_zone": any(sl["warp_zone"] for x in ar for sl in areas[x["key"]]["scroll_locks"]),
            }
    for a in areas.values():
        a["used_by"] = sorted(set(a["used_by"]), key=lambda t: tuple(map(int, t.split("-"))))
        del a["_cols"]
    all_ids = list(stages)
    envs = {
        "full": {"stages": all_ids, "start": "1-1", "note": "the whole game: 1-1 ... 8-4 in order"},
        "random": {"stages": all_ids, "start": None, "note": "a random stage each reset"},
        "lost_levels": {"stages": [], "start": None,
                        "note": "SuperMarioBros2 loads a different ROM (super-mario-bros-2.nes, The Lost Levels); not decoded here"},
    }
    return {"version": VERSION, "note_power_up": NOTE_POWER_UP, "notes": NOTES, "units": {
                "x": "world pixels from the level's left edge (page * 256 + column * 16)",
                "row": "tile row 0-12 (row 11 is the first ground row); y = row * 16 in tile-buffer coordinates",
                "ram_y": "the byte the game holds in Enemy_Y_Position when the object spawns"},
            "source": "SMB1 vanilla ROM (super-mario-bros.nes, as loaded by gym_super_mario_bros), decoded with the format of "
                      "the community disassembly smbdis.asm",
            "areas": areas, "stages": stages, "envs": envs}
