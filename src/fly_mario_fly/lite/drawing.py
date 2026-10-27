"""One video frame: the brain panel on the left (real somata glowing with their group's activity), the game at x2 with the senses' boxes
on it, and a thin strip under the game with the buttons the fly holds. Plain numpy / OpenCV: no font files, no PIL."""
from __future__ import annotations

import cv2
import numpy as np

from fly_mario_fly.lite.panel import PANEL_W
from fly_mario_fly.render.draw import game_panel

STRIP = 24                                   # px under the picture
GREY, DARK = (90, 90, 92), (22, 22, 24)
BUTTONS = ("left", "right", "a", "b")


def frame_size(scale: int, with_panel: bool = True) -> tuple:
    return ((PANEL_W if with_panel else 0) + 256 * scale, 240 * scale + STRIP)


def draw(rec, scale: int, panel=None) -> np.ndarray:
    """`panel`: a lite.panel.Panel for the brain this fly runs on (None: the game alone)."""
    overlay = [it for out in rec.outputs.values() for it in out.overlay]
    img = game_panel(rec.screen, overlay, rec.scroll_x_after, True, scale)
    if panel is not None:
        img = np.hstack([panel.draw(rec.rates, img.shape[0]), img])
    w = img.shape[1]
    strip = np.full((STRIP, w, 3), DARK, np.uint8)
    for j, b in enumerate(BUTTONS):                       # four small squares at the right: lit when the button is held
        x1 = w - 4 - (len(BUTTONS) - j) * 16
        cv2.rectangle(strip, (x1, 6), (x1 + 11, STRIP - 6), (230, 230, 230) if b in rec.buttons else GREY, -1)
    return np.vstack([img, strip])
