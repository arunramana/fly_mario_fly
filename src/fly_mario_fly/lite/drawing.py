"""One video frame: the game picture at x2 with the senses' boxes on it, and a thin strip under it that shows how active
the fly's neurons are (the real wiring, teal) and which buttons are held. Plain numpy / OpenCV: no fonts, no PIL."""
from __future__ import annotations

import cv2
import numpy as np

from fly_mario_fly.render.draw import game_panel

STRIP = 24                                   # px under the picture
TEAL, GREY, DARK = (46, 160, 150), (90, 90, 92), (22, 22, 24)
BUTTONS = ("left", "right", "a", "b")


def frame_size(scale: int) -> tuple:
    return (256 * scale, 240 * scale + STRIP)


def draw(rec, scale: int, groups: list) -> np.ndarray:
    """`groups`: the neuron group names the strip shows, in a fixed order (the same order every frame)."""
    overlay = [it for out in rec.outputs.values() for it in out.overlay]
    img = game_panel(rec.screen, overlay, rec.scroll_x_after, True, scale)
    w = img.shape[1]
    strip = np.full((STRIP, w, 3), DARK, np.uint8)
    n = max(1, len(groups))
    bw = (w - 4 * 16 - 8) // n
    for i, g in enumerate(groups):
        v = float(min(1.0, max(0.0, 3.0 * rec.rates.get(g, 0.0))))      # rates are small (a button fires near 0.1), so x3 fills the bar
        x0 = 4 + i * bw
        cv2.rectangle(strip, (x0, STRIP - 4), (x0 + max(1, bw - 2), STRIP - 4 - max(1, int(v * (STRIP - 8)))), TEAL, -1)
    for j, b in enumerate(BUTTONS):                       # four small squares at the right: lit when the button is held
        x1 = w - 4 - (len(BUTTONS) - j) * 16
        cv2.rectangle(strip, (x1, 6), (x1 + 11, STRIP - 6), (230, 230, 230) if b in rec.buttons else GREY, -1)
    return np.vstack([img, strip])
