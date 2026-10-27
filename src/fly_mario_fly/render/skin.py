"""Draw the player as Luigi: sprites pasted over the game picture. Picture only; the game and the fly never see it.

The player is given as a plain dict (x, y, w, h of the hitbox in level pixels, big, airborne, facing, moving), so this
file names no game object. Sprites sit bottom-centre on the hitbox; frames cycle by frame number."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

DIR = Path(__file__).resolve().parents[3] / "assets" / "sprites" / "luigi"
STATUS_BAR = 32                  # level y has the status bar above it
WALK_EVERY = 4                   # game frames per walk frame


@lru_cache(maxsize=None)
def _sprite(name: str) -> list:
    """[(rgb (h, w, 3), alpha (h, w) bool)] one per animation frame, or [] when the file is missing."""
    out = []
    for f in sorted(DIR.glob(name + ".png")) + sorted(DIR.glob(name + "_[0-9].png")):
        with Image.open(f) as im:
            a = np.asarray(im.convert("RGBA"))
        out.append((a[..., :3].copy(), a[..., 3] > 0))
    return out


def enabled() -> bool:
    return os.environ.get("FLY_MARIO_FLY_SKIN", "luigi").lower() == "luigi" and DIR.is_dir()


def apply(game: np.ndarray, player: dict, scroll_x: float, frame: int) -> np.ndarray:
    """A copy of `game` (240, 256, 3) with the player redrawn as Luigi; `game` itself if no sprite fits."""
    size = "big" if player["big"] else "small"
    pose = "jump" if player["airborne"] else ("walk" if player["moving"] else "stand")
    frames = _sprite(f"{size}_{pose}")
    if not frames:
        return game
    rgb, alpha = frames[(frame // WALK_EVERY) % len(frames)] if pose == "walk" else frames[0]
    if player["facing"] < 0:
        rgb, alpha = rgb[:, ::-1], alpha[:, ::-1]
    h, w = alpha.shape
    cx = int(round(player["x"] - scroll_x + player["w"] / 2))
    bottom = int(round(player["y"] + player["h"])) + STATUS_BAR
    x0, y0 = cx - w // 2, bottom - h
    out = game.copy()
    # wipe the old player: the stock sprite is 16 wide and (16 small / 32 big) tall on the same feet line
    sh, sw = (32 if player["big"] else 16), 16
    ex0, ey0 = max(cx - sw // 2, 0), max(bottom - sh, 0)
    ex1, ey1 = min(cx - sw // 2 + sw, game.shape[1]), min(bottom, game.shape[0])
    if ex1 <= ex0 or ey1 <= ey0:
        return game
    ring = np.concatenate([game[ey0:ey1, max(ex0 - 1, 0)], game[ey0:ey1, min(ex1, game.shape[1] - 1)]])
    bg, n = np.unique(ring, axis=0, return_counts=True)
    out[ey0:ey1, ex0:ex1] = bg[n.argmax()]
    for dy in range(h):
        for dx in range(w):
            y, x = y0 + dy, x0 + dx
            if alpha[dy, dx] and 0 <= y < out.shape[0] and 0 <= x < out.shape[1]:
                out[y, x] = rgb[dy, dx]
    return out
