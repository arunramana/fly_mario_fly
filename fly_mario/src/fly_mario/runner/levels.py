"""The level catalogue: for each of the 35 envs its kind, how far it runs, which object types it holds, and how
saved runs have gone on it.

level_catalogue() never touches the emulator: the kind comes from configs/levels.yaml, the width and object list from
$FLY_MARIO_DATA/levels.json, and a level nobody has scanned yet shows `scanned=False, objects=None, width=None`
(unknown). scan_level(id) scans one level (a walk-right-and-jump driver with enemies switched off, capped in frames
and seconds) and caches it; a scan that stopped before the flag is `partial=True` (width = how far it got, objects =
what it saw up to there). `objects` also includes every type a saved run on that level found (summary.json
`objects_seen`), so a run that got past the scan's reach adds what it met. precompute() scans the levels the yaml lists (1-1, 1-2).
The status part (tried / won / best x) is read from $FLY_MARIO_DATA/runs/*/summary.json on every call.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import yaml

from fly_mario import registry
from fly_mario.fly import connectome as cn
from fly_mario.mario import ram as R
from fly_mario.mario.env import MarioEnv, level_ids
from fly_mario.runner import record

CONFIG = Path(__file__).resolve().parents[3] / "configs" / "levels.yaml"      # fly_mario/configs/levels.yaml
CACHE_VERSION = 2


@dataclass(frozen=True)
class LevelStatus:
    """What saved runs say about a level."""
    attempts: int = 0
    wins: int = 0               # runs that reached the flag
    best_x: float = 0.0         # furthest max_x of any run
    text: str = "not tried"     # "not tried" | "won 2/5" | "best x 1840" (tried, never won)


@dataclass(frozen=True)
class LevelInfo:
    id: str
    kind: str                   # overground | underground | sky | water | castle | mixed (the random-stages env)
    scanned: bool = False
    width: int | None = None    # level pixels: the flag's x if the scan reached it, else how far it got; None = unknown
    flag_x: int | None = None   # x where the scan reached the flag
    partial: bool = False       # the scan stopped before the flag (cap hit or Mario died): width/objects are lower bounds
    stop: str = ""              # why the scan ended: flag | cap | died
    objects: tuple | None = None    # object type names seen, sorted; None = not scanned yet (unknown)
    status: LevelStatus = field(default_factory=LevelStatus)


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def cache_path() -> Path:
    return cn.data_dir() / "levels.json"


def _read_cache() -> dict:
    try:
        d = json.loads(cache_path().read_text(encoding="utf-8"))
        return d["levels"] if d.get("version") == CACHE_VERSION else {}
    except (OSError, ValueError, KeyError):
        return {}


def _write_cache(levels: dict) -> None:
    cache_path().write_text(json.dumps({"version": CACHE_VERSION, "levels": levels}, indent=1), encoding="utf-8")


# ---- the scan ----------------------------------------------------------------------------------------------
class _Driver:
    """Hold Right; jump (A held for a fixed time) when a wall or pit is close. mario/walker.py's rule."""

    def __init__(self):
        self.left = 0

    def act(self, env) -> tuple:
        facts, ram = env.facts, env.ram
        w, g, t = facts["walker"], facts["grid"], facts["tiles"]
        mx = R.mario_x(ram, facts)
        grounded = int(ram[facts["ram"]["player_state"]]) == 0
        walls = [x for x0, x1, _ in R.merged_faces(ram, facts, t["pipe"] + t["step"]) for x in range(x0, x1, g["tile"]) if x >= mx]
        pits = [wx for wx in R.visible_columns(ram, facts) if wx + 1 > mx
                and R.tile(ram, facts, wx, g["ground_row"]) == t["empty"] and R.tile(ram, facts, wx, g["ground_row"] + 1) == t["empty"]]
        near = (walls and min(walls) - mx < w["wall_trigger"]) or (pits and 0 <= min(pits) - mx < w["pit_trigger"])
        if self.left == 0 and near and grounded:
            self.left = w["jump_hold"]
        buttons = ("right", "A") if self.left > 0 else ("right",)
        self.left = max(0, self.left - 1)
        return buttons


def scan_level(level_id: str, env: MarioEnv | None = None) -> dict:
    """Scan one level now and cache it; returns its cache entry {width, flag_x, partial, stop, objects}."""
    sc = config()["scan"]
    own = env is None
    env = env or MarioEnv()
    env.reset(level_id, "v0", 0)
    facts, objects, driver = env.facts, registry.list_plugins("objects"), _Driver()
    seen: set = set()
    max_x, flag_x, stop, t0 = R.mario_x(env.ram, facts), None, "cap", time.monotonic()
    for i in range(int(sc["max_frames"])):
        if i % int(sc["every"]) == 0:
            seen |= {n for n, p in objects.items() if p.find(env.ram, facts)}
        R.sweep_enemies(env, facts)
        st = env.step(driver.act(env))
        max_x = max(max_x, R.mario_x(env.ram, facts))
        if st.info.get("flag_get"):
            flag_x, stop = R.mario_x(env.ram, facts), "flag"
            break
        if st.done:
            stop = "died"
            break
        if time.monotonic() - t0 > float(sc["max_seconds"]):
            break
    if own:
        env.close()
    entry = {"width": int(flag_x if flag_x is not None else max_x), "flag_x": flag_x, "partial": flag_x is None,
             "stop": stop, "objects": sorted(seen)}
    _write_cache({**_read_cache(), level_id: entry})
    return entry


def precompute(levels=None) -> None:
    """Scan the levels named in the yaml (or `levels`) that are not cached yet."""
    todo = [lv for lv in (levels or config()["precompute"]) if lv not in _read_cache()]
    env = MarioEnv() if todo else None
    for lv in todo:
        scan_level(lv, env)
    if env:
        env.close()


def level_objects(level_id: str) -> tuple:
    """The object types in a level: the scan (made the first time it is asked for) plus what saved runs saw there."""
    entry = _read_cache().get(level_id) or scan_level(level_id)
    return tuple(sorted(set(entry["objects"]) | objects_seen_in_runs().get(level_id, set())))


# ---- status from saved runs --------------------------------------------------------------------------------
def level_statuses(runs_dir: Path | None = None) -> dict:
    """{level id: LevelStatus} from every saved run's summary.json."""
    folder = Path(runs_dir) if runs_dir else record.runs_dir()
    tally: dict = {}
    for f in sorted(folder.glob("*/summary.json")) if folder.exists() else ():
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            lv = s["level"]
        except (OSError, ValueError, KeyError):
            continue
        n, w, b = tally.get(lv, (0, 0, 0.0))
        tally[lv] = (n + 1, w + (s.get("outcome") == "flag"), max(b, float(s.get("max_x", 0.0))))
    return {lv: LevelStatus(n, w, b, f"won {w}/{n}" if w else f"best x {b:.0f}") for lv, (n, w, b) in tally.items()}


def objects_seen_in_runs(runs_dir: Path | None = None) -> dict:
    """{level id: object types any saved run on that level found} from the summaries (runs saved before R2 have none)."""
    folder = Path(runs_dir) if runs_dir else record.runs_dir()
    out: dict = {}
    for f in sorted(folder.glob("*/summary.json")) if folder.exists() else ():
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            out.setdefault(s["level"], set()).update(s.get("objects_seen", ()))
        except (OSError, ValueError, KeyError):
            continue
    return out


def _info(lv, cache, kinds, status, seen=None) -> LevelInfo:
    """The scan's objects joined with those any saved run saw (a run that got further than the scan finds more)."""
    e, st, extra = cache.get(lv), status.get(lv, LevelStatus()), (seen or {}).get(lv, set())
    if e is None:
        return LevelInfo(lv, kinds[lv], objects=tuple(sorted(extra)) if extra else None, status=st)
    return LevelInfo(lv, kinds[lv], True, e["width"], e["flag_x"], e["partial"], e["stop"],
                     tuple(sorted(set(e["objects"]) | extra)), st)


def level_info(level_id: str, runs_dir: Path | None = None) -> LevelInfo:
    """One level's catalogue entry; never scans (a level not scanned yet has objects=None)."""
    return _info(level_id, _read_cache(), config()["kinds"], level_statuses(runs_dir), objects_seen_in_runs(runs_dir))


def level_catalogue(runs_dir: Path | None = None) -> list:
    """A LevelInfo for each of the 35 envs, in level_ids() order. Returns at once: nothing is scanned here."""
    cache, kinds, status, seen = _read_cache(), config()["kinds"], level_statuses(runs_dir), objects_seen_in_runs(runs_dir)
    return [_info(lv, cache, kinds, status, seen) for lv in level_ids()]


# ---- thumbnails ---------------------------------------------------------------------------------------------
HUD_ROWS = 32                       # the status bar (score, coins, world, time) above the playfield
MOSAIC = ("1-1", "1-2", "2-2", "1-4")   # the random-stages env picks any stage: its picture is four of them
_thumb_lock = threading.Lock()      # one emulator at a time for thumbnails (a first request makes several)


def thumbnail_path(level_id: str) -> Path:
    return cn.data_dir() / "thumbs" / f"{level_id}.png"


def _first_screen(env: MarioEnv, level_id: str) -> np.ndarray:
    return env.reset(level_id, "v0", 0).frame[HUD_ROWS:]            # (208, 256, 3): the playfield as the level opens


def level_thumbnail(level_id: str) -> bytes:
    """PNG (256 x 208) of the level's opening screen, status bar cropped. Made once with the emulator, then read from
    $FLY_MARIO_DATA/thumbs/. The random-stages env has no single opening screen, so it gets a 2 x 2 mosaic of four stages.
    KeyError for an id that is not in the catalogue."""
    if level_id not in level_ids():
        raise KeyError(f"no level {level_id!r}")
    path = thumbnail_path(level_id)
    with _thumb_lock:
        if path.exists():
            return path.read_bytes()
        env = MarioEnv()
        try:
            if level_id == "random":
                tiles = [cv2.resize(_first_screen(env, lv), (128, 104), interpolation=cv2.INTER_AREA) for lv in MOSAIC]
                img = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])])
            else:
                img = _first_screen(env, level_id)
        finally:
            env.close()
        ok, buf = cv2.imencode(".png", cv2.cvtColor(np.ascontiguousarray(img), cv2.COLOR_RGB2BGR))
        assert ok
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(buf.tobytes())
        return buf.tobytes()
