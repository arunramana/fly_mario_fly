"""Read-only survey: how does the far_edge_tower loom shape look on every pit in the game?

For each of the 32 stages the scripted walker (mario/walker.py, enemies switched off) walks the level. At every pit
it saves two annotated frames, ~120 px before the near edge and at take-off, drawing the pit's raw box (white), the
rim tops the sense uses (cyan), the tower box (red) and the looming wedge from Mario's eye (red). A CSV classifies
each pit; one contact sheet per world. Nothing in src/ is touched or changed.

    python tools/pit_gallery.py                  -> $FLY_MARIO_DATA/pit_gallery/
    python tools/pit_gallery.py --levels 1-1 3-1 --workers 4
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml                                                                   # noqa: E402

from fly_mario import registry                                                # noqa: E402
from fly_mario.contracts import ObjectInstance                                # noqa: E402
from fly_mario.mario import ram as R                                          # noqa: E402
from fly_mario.mario.env import MarioEnv                                      # noqa: E402
from fly_mario.mario.walker import Walker                                     # noqa: E402
from fly_mario.senses.kit.geom import eye_of, gap, theta_of                   # noqa: E402
from fly_mario.senses.kit.memory import SenseMemory                           # noqa: E402

HUD, SCALE = 32, 3                  # the status bar is 32 px; frames are drawn at 3x
APPROACH = 120                      # px between Mario's front and the near edge for the first frame
TAKEOFF_WINDOW = 48                 # a jump counts as a pit take-off when the pit's near edge is this close
WALKER_VARIANTS = [(None, None), (32, 28), (16, 28), (40, 40)]   # (pit_trigger, jump_hold); None = the facts
WHITE, CYAN, RED, YELLOW = "#ffffff", "#00e5ff", "#ff3030", "#ffee00"
WATER = {lv for lv, k in yaml.safe_load((Path(__file__).resolve().parents[1] / "configs" / "levels.yaml")
                                        .read_text(encoding="utf-8"))["kinds"].items() if k == "water"}


def out_dir() -> Path:
    return Path(os.environ["FLY_MARIO_DATA"]) / "pit_gallery"


# ---- geometry -------------------------------------------------------------------------------------------------
def hull(points):
    pts = sorted(set(points))
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h[:-1]
    return half(pts) + half(pts[::-1])


def material(ram, facts, wx: int, y: int) -> str:
    """What the rim's top tile is made of (facts' tile groups, else its raw id)."""
    t = R.tile(ram, facts, wx, int(y) // facts["grid"]["tile"])
    for name in ("pipe", "step", "brick", "qblock", "used_block", "ceiling_block"):
        if t in facts["tiles"][name]:
            return name
    return "floor" if t == facts["tiles"]["ground"] else f"tile{t}"


def on_solid_top(ram, facts, wx: int, y: int) -> bool:
    """The rim y really is the top of a solid tile: solid at y, not solid just above it."""
    t, row = facts["grid"]["tile"], int(y) // facts["grid"]["tile"]
    return R.is_solid(facts, R.tile(ram, facts, wx, row)) and not (row > 0 and R.is_solid(facts, R.tile(ram, facts, wx, row - 1)))


def classify(ram, facts, pit: ObjectInstance, shape, knobs) -> dict:
    """Everything the CSV says about one pit, from one frame where the pit is fully on screen."""
    b, tile = pit.box, facts["grid"]["tile"]
    near_y, far_y = pit.state["rims"]
    ground = pit.state["ground"]
    tw = shape.shape(ObjectInstance(pit.type, pit.id, b, pit.side, {**pit.state, "loom_rims": (near_y, far_y)}), facts, knobs)
    cols = range(int(b.x), int(b.x + b.w), tile)                    # the pit's own columns only (not the rim stairs)
    jump_rows = range(facts["grid"]["stand_row"] - 5, facts["grid"]["stand_row"])
    ceiling = any(R.tile(ram, facts, wx, r) != facts["tiles"]["empty"] for wx in cols for r in jump_rows)
    return dict(x=int(b.x), width=int(b.w), open=bool(pit.state.get("open")), ground=int(ground),
                near_rim_h=int(ground - near_y), far_rim_h=int(ground - far_y),
                near_rim_made_of=material(ram, facts, b.x - tile, near_y), far_rim_made_of=material(ram, facts, b.x + b.w, far_y),
                rims_on_solid_tops=bool(on_solid_top(ram, facts, b.x - tile, near_y) and (pit.state["open"] or on_solid_top(ram, facts, b.x + b.w, far_y))),
                tower_h=int(tw.h), tower_base_above_ground=int(ground - (tw.y + tw.h)),
                tower_top_above_far_rim=int(far_y - tw.y), tower_reaches_far_rim_top=bool(tw.y <= far_y), tower_y=int(tw.y),
                too_wide=bool(pit.state["too_wide"]), lift_near=bool(pit.state["lift_near"]), ceiling_in_jump_zone=bool(ceiling))


# ---- drawing --------------------------------------------------------------------------------------------------
def render(frame, ram, facts, mario, pit, tower, rims, theta, label, is_open=False):
    left = int(ram[facts["ram"]["screen_page"]]) * 256 + int(ram[facts["ram"]["screen_x"]])
    img = Image.fromarray(frame).convert("RGB").resize((256 * SCALE, 240 * SCALE), Image.NEAREST)
    d = ImageDraw.Draw(img, "RGBA")
    sx = lambda x: (x - left) * SCALE                       # noqa: E731
    sy = lambda y: (y + HUD) * SCALE                        # noqa: E731

    def box(b, colour, width=2, dash=False):
        x0, y0, x1, y1 = sx(b.x), sy(b.y), sx(b.x + b.w), sy(b.y + b.h)
        if not dash:
            d.rectangle([x0, y0, x1, y1], outline=colour, width=width)
        else:
            for xa in range(int(x0), int(x1), 8):
                d.line([xa, y0, min(xa + 4, x1), y0], fill=colour, width=width)
                d.line([xa, y1, min(xa + 4, x1), y1], fill=colour, width=width)
            for ya in range(int(y0), int(y1), 8):
                d.line([x0, ya, x0, min(ya + 4, y1)], fill=colour, width=width)
                d.line([x1, ya, x1, min(ya + 4, y1)], fill=colour, width=width)

    ex, ey = eye_of(mario)
    corners = [(sx(tower.x), sy(tower.y)), (sx(tower.x + tower.w), sy(tower.y)),
               (sx(tower.x), sy(tower.y + tower.h)), (sx(tower.x + tower.w), sy(tower.y + tower.h))]
    d.polygon(hull([(sx(ex), sy(ey))] + corners), fill=(255, 48, 48, 60), outline=(255, 48, 48, 200))
    box(pit, WHITE, 2, dash=True)
    box(tower, RED, 3)
    near_y, far_y = rims
    t = facts["grid"]["tile"]
    d.line([sx(pit.x - t), sy(near_y), sx(pit.x), sy(near_y)], fill=CYAN, width=4)
    d.line([sx(pit.x + pit.w), sy(far_y), sx(pit.x + pit.w + t), sy(far_y)], fill=CYAN, width=4)
    d.rectangle([sx(mario.x), sy(mario.y), sx(mario.x + mario.w), sy(mario.y + mario.h)], outline="#00a0ff", width=2)
    d.text((6, 6 * SCALE + 4), f"{label}   theta={theta:.2f} rad" + ("   (pit runs off the screen edge)" if is_open else ""),
           fill=YELLOW)
    return img


# ---- one level ------------------------------------------------------------------------------------------------
def walk(level: str, variant: tuple, found: dict, folder: Path, tiles: set) -> str:
    """One walker pass; fills `found` (pit x -> record) with shots of the pits it has not yet got. Returns why it ended."""
    env = MarioEnv()
    st = env.reset(level, "v0", 0)
    facts = env.facts
    pit_plug, pit_shape = registry.list_plugins("objects")["pit"], registry.list_plugins("shapes")["far_edge_tower"]
    terrain = [p for p in registry.list_plugins("objects").values() if p.kind == "terrain"]
    loom = registry.list_plugins("senses")["looming"]
    knobs = {k.key: k.default for s in (loom, pit_shape) for k in s.knobs}
    mem = SenseMemory()
    mem.rng, mem.sigma, mem.mods = None, 0.0, {}
    drive, grounded_prev = Driver(), True
    if variant[0] is not None:
        facts = type(facts)(facts)
        facts["walker"] = {**facts["walker"], "pit_trigger": variant[0], "jump_hold": variant[1]}
    stop = "frames"
    for i in range(facts["walker"]["max_frames"]):
        ram = st.ram
        mario = R.read_mario(ram, facts)
        if i % 4 == 0:
            tiles |= {R.tile(ram, facts, wx, r) for wx in R.visible_columns(ram, facts) for r in range(13)}
        world = [o for p in terrain for o in p.find(ram, facts)]
        pits = [o for o in world if o.type == "pit"]
        mem.world = world
        out = loom.cue(pits, mario, facts, knobs, mem)                # keeps the sense's own memory in step (ground, released)
        first_col = (int(ram[facts["ram"]["screen_page"]]) * 256 + int(ram[facts["ram"]["screen_x"]])) // facts["grid"]["tile"]             * facts["grid"]["tile"]
        for p in pits:
            # The finder sees only the visible columns, so a pit scrolling off the left edge reappears as a "new",
            # narrower pit starting at the first column. It is the rest of a pit already recorded: skip it.
            if p.box.x == first_col and any(x < p.box.x <= x + r["wmax"] for x, r in found.items()):
                continue
            rec = found.setdefault(int(p.box.x), dict(level=level, shots={}, lift_near=False, walker=variant, wmax=0))
            rec["wmax"] = max(rec["wmax"], int(p.box.w))
            front_gap = p.box.x - (mario.x + mario.w)
            rims = p.state["rims"]
            rec["lift_near"] = rec["lift_near"] or p.state["lift_near"]
            tower = pit_shape.shape(ObjectInstance("pit", p.id, p.box, p.side,
                                                   {**p.state, "loom_rims": rims}), facts, knobs)
            takeoff = mario.airborne and grounded_prev
            want = None
            if front_gap <= APPROACH and not p.state.get("open") and "approach" not in rec["shots"] and front_gap > 0 \
                    and (not mario.airborne or front_gap <= 64):       # from the ground he walks on, unless he is nearly there
                want = "approach"
            elif takeoff and -mario.w < front_gap <= TAKEOFF_WINDOW and "takeoff" not in rec["shots"]:
                want = "takeoff"
            if want == "approach" or "meta" not in rec or (rec["meta"]["open"] and not p.state.get("open")):
                rec["meta"] = classify(ram, facts, p, pit_shape, knobs)       # classified from the approach frame; provisional before it
            if want:
                h = mario.y + mario.h - tower.y
                th = theta_of(gap(mario, tower.x, tower.y, tower.w, tower.h), max(h, 0.0))
                img = render(st.frame, ram, facts, mario, p.box, tower, rims, th,
                             f"{level} x={int(p.box.x)} {want} gap={int(front_gap)}", bool(p.state.get("open")))
                path = folder / f"{level}_x{int(p.box.x):05d}_{want}.png"
                img.save(path)
                rec["shots"][want] = path.name
        grounded_prev = not mario.airborne
        R.sweep_enemies(env, facts)
        st = env.step(drive.act(env, facts, i))
        if drive.stuck(i):
            stop = "stuck"
            break
        if st.done:
            stop = "died"
            break
        if st.info.get("flag_get"):
            stop = "flag"
            break
    env.close()
    return f"{stop}@x={R.mario_x(st.ram, facts)}"


class Driver:
    """mario/walker.py's Walker (with this pass's trigger distances), plus an unstick routine: this is scenery work,
    not the fly. After UNSTICK_AFTER frames without new ground it jumps while running, with the hold cycling short /
    long / medium, so walls and stairs the plain walker stalls on (other levels use other tile ids) are still climbed."""
    HOLDS = (28, 44, 14, 60)
    UNSTICK_AFTER, GIVE_UP = 40, 700

    def __init__(self):
        self.walker, self.best, self.last_progress, self.k, self.hold = Walker(), -1, 0, 0, 0

    def act(self, env, facts, i):
        class _E:                                                   # Walker reads env.facts / env.ram
            ram = env.ram
        _E.facts = facts
        x = R.mario_x(env.ram, facts)
        if x > self.best:
            self.best, self.last_progress = x, i
        grounded = int(env.ram[facts["ram"]["player_state"]]) == 0
        if self.hold == 0 and grounded and i - self.last_progress > self.UNSTICK_AFTER:
            self.hold = self.HOLDS[self.k % len(self.HOLDS)]
            self.k += 1
            self.last_progress = i - self.UNSTICK_AFTER + 15        # try again in 15 frames if it did not help
        if self.hold > 0:
            self.hold -= 1
            self.walker.hold = 0
            return ("right", "A", "B")
        return self.walker.act(_E)

    def stuck(self, i):
        return i - self.last_progress > self.GIVE_UP


def do_level(level: str) -> dict:
    folder = out_dir() / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    found: dict = {}
    notes, tiles = [], set()
    for v in WALKER_VARIANTS:
        before = set(found)
        end = walk(level, v, found, folder, tiles)
        notes.append(f"walker{v}: {end}, +{len(set(found) - before)} pits")
        if end.startswith("flag") and all(len(r["shots"]) == 2 for r in found.values()):
            break
    return dict(level=level, pits=found, notes=notes, tiles=sorted(int(t) for t in tiles))


# ---- sheets and csv -------------------------------------------------------------------------------------------
def oddities(level: str, m: dict, rec: dict) -> list:
    odd = []
    if m.get("too_wide"):
        odd.append("wider than a jump")
    if m.get("near_rim_h") != m.get("far_rim_h"):
        odd.append("uneven rims")
    if m and not m.get("rims_on_solid_tops", True):
        odd.append("sense misses a rim (rim is not on a solid tile top)")
    if m.get("tower_base_above_ground", 0) < -16:
        odd.append("tower base more than a tile below the take-off ground")
    if m.get("ceiling_in_jump_zone"):
        odd.append("solid tiles above the hole (platform or ceiling)")
    if level in WATER:
        odd.append("water level")
    if rec.get("lift_near"):
        odd.append("lift near the pit (approximate type range)")
    if m.get("open"):
        odd.append("only seen running off the screen edge")
    if not m.get("tower_reaches_far_rim_top", True):
        odd.append("tower does not reach far rim top")
    if len(rec["shots"]) < 2:
        odd.append("missing frame: " + ",".join(s for s in ("approach", "takeoff") if s not in rec["shots"]))
    return odd


def build(results: list) -> None:
    root, rows, per_world = out_dir(), [], {}
    for res in sorted(results, key=lambda r: r["level"]):
        lv = res["level"]
        for n, (x, rec) in enumerate(sorted(res["pits"].items()), 1):
            m = rec.get("meta", {})
            odd = oddities(lv, m, rec)
            rows.append(dict(level=lv, n=n, label=f"{lv} #{n} x={x}", **{k: m.get(k, "") for k in (
                "x", "width", "ground", "near_rim_h", "far_rim_h", "near_rim_made_of", "far_rim_made_of", "rims_on_solid_tops",
                "tower_h", "tower_base_above_ground", "tower_top_above_far_rim", "tower_reaches_far_rim_top", "too_wide", "lift_near",
                "ceiling_in_jump_zone")},
                oddities="; ".join(odd), frame_approach=rec["shots"].get("approach", ""), frame_takeoff=rec["shots"].get("takeoff", "")))
            rows[-1]["x"] = x
            per_world.setdefault(lv[0], []).append((rows[-1], rec))
    cols = list(rows[0])
    with open(root / "pits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    cell_w, cell_h = 256 * 2, 240 * 2
    for world, items in sorted(per_world.items()):
        per_row = 2                                              # two pits per row, each = approach + takeoff
        nrows = (len(items) + per_row - 1) // per_row
        sheet = Image.new("RGB", (per_row * 2 * cell_w, nrows * (cell_h + 22)), "#202020")
        d = ImageDraw.Draw(sheet)
        for k, (row, rec) in enumerate(items):
            ox, oy = (k % per_row) * 2 * cell_w, (k // per_row) * (cell_h + 22)
            d.text((ox + 6, oy + 4), row["label"] + (f"   w={row['width']}  rims {row['near_rim_h']}/{row['far_rim_h']}  "
                   f"tower {row['tower_h']}  " + row["oddities"] if row["width"] != "" else "   " + row["oddities"]), fill=YELLOW)
            for j, key in enumerate(("approach", "takeoff")):
                if key in rec["shots"]:
                    im = Image.open(root / "frames" / rec["shots"][key]).resize((cell_w, cell_h), Image.LANCZOS)
                    sheet.paste(im, (ox + j * cell_w, oy + 22))
        sheet.save(root / f"sheet_world{world}.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", nargs="*", default=[f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--rebuild", action="store_true", help="only redo the CSV and sheets from results.json")
    a = ap.parse_args()
    out_dir().mkdir(parents=True, exist_ok=True)
    cache = out_dir() / "results.json"
    if a.rebuild:
        results = json.loads(cache.read_text())
    else:
        with ProcessPoolExecutor(a.workers) as ex:
            results = list(ex.map(do_level, a.levels))
        cache.write_text(json.dumps(results, indent=1))
    for r in results:
        print(r["level"], len(r["pits"]), "pits;", " | ".join(r["notes"]))
    build(results)
    print(out_dir())


if __name__ == "__main__":
    main()
