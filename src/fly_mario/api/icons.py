"""Object icons: a crop of the game picture, made from the emulator the first time they are asked for.

For each object type of the registry, play a walking fly through a level that holds it (enemies removed unless the
type is an enemy) until an instance is fully on screen with Mario clear of it, and crop its box from the picture the
senses saw. A box taller than a block keeps its top part (a pipe's mouth); a box with a gap keeps a little of its rims.
The crop is scaled up with nearest-neighbour (crisp pixels) onto a transparent square and cached as
$FLY_MARIO_DATA/icons/<type>.png. Nothing is committed: like the game picture, the icons come from the emulator.

This file names no object: what to crop is the object's own box and kind, as the runner reports them.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from fly_mario import registry
from fly_mario.contracts import Scene
from fly_mario.runner import Run, level_catalogue, load_fly
from fly_mario.runner.record import runs_dir

ICON = 80                      # output size, px
STATUS_BAR = 32                # level y has the 32 px status bar above it (as the renderer draws it)
PAD = 4                        # px of the surroundings kept around a box (rims of a gap)
MAX_SIDE = 32                  # a box taller / wider than this keeps its top / middle (two blocks)
WALKER = "champion_e1s"        # the preset that walks a level (any fly that moves would do)
MAX_FRAMES = 2400
_lock = threading.Lock()
_tried: set = set()            # types a generation pass has already looked for in this process


def icons_dir() -> Path:
    return runs_dir().parent / "icons"


def icon_path(name: str) -> Path:
    return icons_dir() / f"{name}.png"


def crop_box(box, scroll_x: float) -> Optional[tuple]:
    """(x0, y0, x1, y1) of the crop on the 256 x 240 screen, or None if the box is not fully on it."""
    sx, sy = box.x - scroll_x, box.y + STATUS_BAR
    if sx < 0 or sy < 0 or sx + box.w > 256 or sy + box.h > 240:
        return None
    w, h = min(box.w, MAX_SIDE * 2), min(box.h, MAX_SIDE)               # tall: keep the top; wide: keep the middle
    x0 = sx + (box.w - w) / 2
    return (int(max(0, x0 - PAD)), int(max(0, sy - PAD)), int(min(256, x0 + w + PAD)), int(min(240, sy + h + PAD)))


def to_icon(crop: np.ndarray) -> np.ndarray:
    """RGB crop -> ICON x ICON BGRA, scaled by a whole factor with nearest-neighbour, centred, transparent padding."""
    h, w = crop.shape[:2]
    k = max(1, ICON // max(h, w))
    big = np.repeat(np.repeat(crop, k, axis=0), k, axis=1)
    out = np.zeros((ICON, ICON, 4), np.uint8)
    y0, x0 = (ICON - big.shape[0]) // 2, (ICON - big.shape[1]) // 2
    out[y0:y0 + big.shape[0], x0:x0 + big.shape[1], :3] = big[..., ::-1]
    out[y0:y0 + big.shape[0], x0:x0 + big.shape[1], 3] = 255
    return out


def _levels_holding(types: set) -> list:
    """Scanned levels that hold any of the types, most useful first."""
    cat = [lv for lv in level_catalogue() if lv.objects and types & set(lv.objects)]
    return sorted(cat, key=lambda lv: (-len(types & set(lv.objects)), lv.id))


def _play(level_id: str, want: set, enemies: bool, found: dict) -> None:
    """One run of a walking fly; fills `found` {type: BGRA icon} for the wanted types it passes."""
    mods = () if enemies else (("no_enemies", {}),)
    run = Run(load_fly(WALKER), Scene(level_id=level_id, modifiers=mods, max_frames=MAX_FRAMES))
    prev = None
    while not run.finished and want - set(found):
        rec = run.step()
        for t in want - set(found):
            for o in rec.found.get(t, ()):
                if prev is None or o.state.get("open"):
                    continue
                c = crop_box(o.box, rec.scroll_x)
                m = rec.mario
                mario_in = c and (m.x - rec.scroll_x < c[2] and m.x - rec.scroll_x + m.w > c[0] and m.y < c[3] and m.y + m.h > c[1])
                if c and not mario_in:
                    found[t] = to_icon(prev[c[1]:c[3], c[0]:c[2]])
                    break
        prev = rec.screen


def make_icons(names: list) -> dict:
    """Make the icons for these object types (those not cached); returns {type: path} for the ones that exist."""
    kinds = {n: registry.list_plugins("objects")[n].kind for n in names}
    todo = {n for n in names if not icon_path(n).exists()}
    found: dict = {}
    for enemies in (False, True):
        want = {n for n in todo if (kinds[n] == "enemy") == enemies}
        for lv in _levels_holding(want):
            if not want - set(found):
                break
            try:
                _play(lv.id, want, enemies, found)
            except Exception:                                     # noqa: BLE001 - an icon that cannot be made is a plain square
                continue
    icons_dir().mkdir(parents=True, exist_ok=True)
    for n, img in found.items():
        ok, buf = cv2.imencode(".png", img)
        if ok:
            icon_path(n).write_bytes(buf.tobytes())
    return {n: icon_path(n) for n in names if icon_path(n).exists()}


def get_icon(name: str) -> Optional[Path]:
    """The icon's file, made now if need be (one pass makes every missing icon); None if it cannot be made."""
    if name not in registry.list_plugins("objects"):
        raise KeyError(f"no object type {name!r}")
    if icon_path(name).exists():
        return icon_path(name)
    with _lock:
        if not icon_path(name).exists() and name not in _tried:
            missing = [n for n in registry.list_plugins("objects") if not icon_path(n).exists()]
            _tried.update(missing)
            make_icons(missing)
    return icon_path(name) if icon_path(name).exists() else None
