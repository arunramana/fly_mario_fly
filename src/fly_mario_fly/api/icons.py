"""Object icons: a crop of the game picture, made from the emulator and cached.

For each object type of the registry, a walking fly is played through a level that holds it (overground levels first,
so colours match 1-1; enemies removed unless the type is an enemy) until an instance is shown well: fully on screen,
Mario clear of it and, for enemies and pickups, moving on its own and clear of every other object (a mushroom that has
left its block, a whole Koopa). The crop is its box, plus a little of its surroundings (a pit's rims); a box taller
than a block keeps its top (a pipe's mouth). The level's background colour becomes transparent, the crop is scaled
saved at its NATIVE size (no padding, no scaling) as $FLY_MARIO_FLY_DATA/icons/<type>.png the moment it is found; the page
scales it by a whole factor so the pixels stay crisp. A type whose picture is the same as another type's is looked for in other places first; if it
really is the same art, icons/notes.json says so. Nothing is committed: like the game picture, icons come from the emulator.

The work runs in its own process (`python -m fly_mario_fly.api.icons`, started when the API starts) so that serving never
waits for the emulator; until a file exists the endpoint answers 404 and the page shows a plain square.
This file names no object: what to crop is the object's own box and kind, as the runner reports them.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml
from PIL import Image

from fly_mario_fly import registry
from fly_mario_fly.contracts import Scene
from fly_mario_fly.runner import atomic, Run, level_catalogue, load_fly
from fly_mario_fly.runner.record import runs_dir

STATUS_BAR = 32                # level y has the 32 px status bar above it (as the renderer draws it)
PAD = 4                        # px of the surroundings kept around a box (rims of a gap)
SPRITE_PAD = 2                 # px of margin around a sprite, so no edge of it touches the crop's edge
MAX_SIDE = 32                  # a box taller / wider than this keeps its top / middle (two blocks)
WALKER = "champion_e1s"        # the preset that walks a level (any fly that moves would do)
MAX_FRAMES = 2400
FRESH = 1200.0                 # seconds a "making" lock is believed


def icons_dir() -> Path:
    return runs_dir().parent / "icons"


def icon_path(name: str) -> Path:
    return icons_dir() / f"{name}.png"


MAP = Path(__file__).resolve().parents[3] / "configs" / "icons.yaml"      # object type -> sprite file name


def sprites_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "sprites"


def sprite_icon(name: str) -> Optional[np.ndarray]:
    """The downloaded sprite mapped to this type in configs/icons.yaml as a BGRA at its native size (a GIF's first frame);
    None if there is no mapping or no file."""
    try:
        file = (yaml.safe_load(MAP.read_text(encoding="utf-8")) or {}).get(name)
        path = sprites_dir() / file if file else None
        if path is None or not path.is_file():
            return None
        with Image.open(path) as im:
            im.seek(0)
            rgba = np.array(im.convert("RGBA"))
    except (OSError, ValueError, yaml.YAMLError):
        return None
    return np.ascontiguousarray(rgba[..., [2, 1, 0, 3]])


def crop_box(box, scroll_x: float, pad: int = PAD) -> Optional[tuple]:
    """(x0, y0, x1, y1) of the crop on the 256 x 240 screen, or None if the box is not fully on it."""
    sx, sy = box.x - scroll_x, box.y + STATUS_BAR
    if sx < 0 or sy < 0 or sx + box.w > 256 or sy + box.h > 240:
        return None
    w, h = min(box.w, MAX_SIDE * 2), min(box.h, MAX_SIDE)               # tall: keep the top; wide: keep the middle
    x0 = sx + (box.w - w) / 2
    return (int(max(0, x0 - pad)), int(max(0, sy - pad)), int(min(256, x0 + w + pad)), int(min(240, sy + h + pad)))


def background(screen: np.ndarray) -> tuple:
    """The level's background colour: the most common colour below the status bar."""
    px = screen[STATUS_BAR:].reshape(-1, 3)
    cols, n = np.unique(px, axis=0, return_counts=True)
    return tuple(int(v) for v in cols[n.argmax()])


def to_icon(crop: np.ndarray, bg: Optional[tuple] = None) -> np.ndarray:
    """RGB crop -> BGRA at the crop's own size: pixels of the background colour transparent."""
    alpha = np.full(crop.shape[:2], 255, np.uint8)
    if bg is not None:
        alpha[(crop == np.array(bg, np.uint8)).all(axis=2)] = 0
    return np.dstack([crop[..., ::-1], alpha])


def _levels_holding(types: set) -> list:
    """Scanned levels that hold any of the types: overground first (1-1's colours), then by id."""
    cat = [lv for lv in level_catalogue() if lv.objects and types & set(lv.objects)]
    return sorted(cat, key=lambda lv: (lv.kind != "overground", lv.id))


ALIKE = 0.3                    # two 16 x 16 pictures with fewer than this fraction of differing pixels are the same art


def _alike(a: str, b: str) -> bool:
    x, y = np.frombuffer(bytes.fromhex(a), np.uint8), np.frombuffer(bytes.fromhex(b), np.uint8)
    return x.size == y.size and (x.reshape(-1, 3) != y.reshape(-1, 3)).any(axis=1).mean() < ALIKE


def _overlap(a, b) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


class Maker:
    """Finds the pictures; `save` is called with each icon the moment it is found."""

    def __init__(self, kinds: dict, save, sigs: dict):
        self.kinds, self.save, self.sigs = kinds, save, sigs
        self.dups: dict = {}                       # type -> (icon, signature, same-as): the first candidate that looked like another type's

    def _good(self, t, o, rec, prev_x, others) -> Optional[tuple]:
        if o.state.get("open") or o.state.get("shell"):
            return None
        sprite = self.kinds[t] in ("enemy", "pickup")                           # a sprite is cropped tight; a tile keeps its surroundings
        scroll = rec.scroll_x_after                                             # rec.screen is the picture after the action
        c = crop_box(o.box, scroll, SPRITE_PAD if sprite else PAD)
        if c is None:
            return None
        m = rec.mario
        if m.x - scroll < c[2] and m.x - scroll + m.w > c[0] and m.y + STATUS_BAR < c[3] and m.y + m.h + STATUS_BAR > c[1]:
            return None                                                    # Mario is in the way
        if sprite:
            if prev_x.get((t, o.id)) in (None, o.box.x) or any(_overlap(o.box, p.box) for p in others):
                return None                                                # still in its block, or standing still
        return c

    def play(self, level_id: str, want: set, enemies: bool) -> None:
        mods = () if enemies else (("no_enemies", {}),)
        run = Run(load_fly(WALKER), Scene(level_id=level_id, modifiers=mods, max_frames=MAX_FRAMES))
        prev_x = {}
        while not run.finished and want:
            rec = run.step()
            screen, bg = rec.screen, background(rec.screen)
            for t in sorted(want):
                for o in rec.found.get(t, ()):
                    others = [p for n, objs in rec.found.items() if n != t for p in objs]
                    c = self._good(t, o, rec, prev_x, others)
                    if c is None:
                        continue
                    sx, sy = int(o.box.x - rec.scroll_x_after), int(o.box.y + STATUS_BAR)
                    sig = screen[sy:sy + 16, sx:sx + 16].tobytes().hex()
                    icon = to_icon(screen[c[1]:c[3], c[0]:c[2]], bg)
                    same = next((n for n, s in self.sigs.items() if n != t and self.kinds[n] == self.kinds[t] == "terrain" and _alike(s, sig)), None)
                    if same:
                        self.dups.setdefault(t, (icon, sig, same))
                        continue
                    self.sigs[t] = sig
                    self.save(t, icon, None)
                    want = want - {t}
                    break
            prev_x = {(t, o.id): o.box.x for t, objs in rec.found.items() for o in objs}

    def run(self, names: set) -> None:
        for enemies in (False, True):
            want = {n for n in names if (self.kinds[n] == "enemy") == enemies}
            for lv in _levels_holding(want):
                if not want:
                    break
                try:
                    self.play(lv.id, want, enemies)
                except Exception:                                    # noqa: BLE001 - an icon that cannot be made is a plain square
                    continue
                want = {n for n in want if n not in self.sigs}
        for t, (icon, sig, same) in self.dups.items():
            if t not in self.sigs:                                   # looked for elsewhere, found nothing different
                self.sigs[t] = sig
                self.save(t, icon, f"the same picture as {same}")


def make_icons(names: list) -> dict:
    """Make the icons for these object types (those not cached), saving each as it is found; {type: path} of those that exist."""
    d = icons_dir()
    d.mkdir(parents=True, exist_ok=True)
    notes = _read(d / "notes.json")

    def save(name, img, note):
        ok, buf = cv2.imencode(".png", img)
        if ok:
            atomic.write_bytes(icon_path(name), buf.tobytes())
        if note:
            notes[name] = note
        atomic.write_json(d / "notes.json", notes)
        atomic.write_json(d / "sigs.json", maker.sigs if maker else sigs)

    kinds = {n: o.kind for n, o in registry.list_plugins("objects").items()}
    todo = {n for n in names if not icon_path(n).exists()}
    maker, sigs = None, _read(d / "sigs.json")
    for n in sorted(todo):
        img = sprite_icon(n)                                                 # a downloaded sprite, when there is one
        if img is not None:
            save(n, img, None)
    todo = {n for n in todo if not icon_path(n).exists()}
    maker =Maker(kinds, save, {n: s for n, s in _read(d / "sigs.json").items() if n not in todo})
    maker.run(todo)
    return {n: icon_path(n) for n in names if icon_path(n).exists()}


def _read(path: Path) -> dict:
    return atomic.read_json(path) or {}


def get_icon(name: str) -> Optional[Path]:
    """The icon's file if it has been made; None (the page shows a plain square). Never waits for the emulator."""
    if name not in registry.list_plugins("objects"):
        raise KeyError(f"no object type {name!r}")
    return icon_path(name) if icon_path(name).exists() else None


# ---- the background process ---------------------------------------------------------------------------------------------
def ensure_generating() -> bool:
    """Start the icon process unless every icon exists or one is already running. True if it was started."""
    names = list(registry.list_plugins("objects"))
    if all(icon_path(n).exists() for n in names):
        return False
    d = icons_dir()
    d.mkdir(parents=True, exist_ok=True)
    lock = d / ".making"
    if lock.exists() and time.time() - lock.stat().st_mtime < FRESH:
        return False
    lock.write_text(str(time.time()))
    src = str(Path(__file__).resolve().parents[2])
    kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    log = open(d / "log.txt", "ab")
    subprocess.Popen([sys.executable, "-m", "fly_mario_fly.api.icons"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     env={**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")]))}, **kw)
    log.close()
    return True


def main() -> int:
    names = list(registry.list_plugins("objects"))
    try:
        got = make_icons(names)
        print("icons:", sorted(got), "missing:", sorted(set(names) - set(got)), flush=True)
    finally:
        (icons_dir() / ".making").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
