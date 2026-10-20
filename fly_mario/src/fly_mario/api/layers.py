"""The picture of a live run, as separate layers the browser stacks: the brain panel (JPEG), the game screen (PNG,
256 x 240, drawn at x4 by the page) and the sense overlay (transparent PNG at the game's x4 size). Keeping the layers
apart is what lets "Show senses" and "Show brain" toggle instantly in the browser.

The brain panel is render.draw.BrainPanel (the approved R3 look). The overlay follows render.draw.game_panel's
geometry, drawn straight onto a transparent RGBA canvas: game_panel composites onto the game picture, which a layer
cannot, and doing it twice to recover the alpha costs 14 ms a frame. tests/test_ui_layers.py checks that the two agree.
Talks to the runner and render only; names no sense or object.
"""
from __future__ import annotations

import struct
import threading
import zlib
from types import SimpleNamespace
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from fly_mario.render import source
from fly_mario.render.draw import COL_W, COL_X, GAME_H, GAME_W, TEXT_Y, BrainPanel, hex_rgb

SMOOTH = 3                     # the glow and the index use a 3-frame mean of the rates (render.source.SMOOTH)
JPEG_QUALITY = 82
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


DASH = {"dashed": (14, 9), "dotted": (3, 7)}          # (on, off) px, the same as render.draw


def _line(img, p0, p1, col, width, style) -> None:
    """A solid, dashed or dotted anti-aliased line (screen pixels)."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    pt = lambda v: (int(round(v[0])), int(round(v[1])))
    if style == "solid":
        cv2.line(img, pt(p0), pt(p1), col, width, cv2.LINE_AA)
        return
    on, off = DASH[style]
    length = float(np.hypot(*(p1 - p0)))
    if length == 0:
        return
    u, t = (p1 - p0) / length, 0.0
    while t < length:
        cv2.line(img, pt(p0 + u * t), pt(p0 + u * min(t + on, length)), col, width, cv2.LINE_AA)
        t += on + off


def overlay_rgba(overlay: list, scroll_x: float) -> Optional[tuple]:
    """The sense overlay on a transparent canvas the size of the game at x4 (960 x 1024), cropped to what was drawn.

    Returns (rgba crop, x, y) with (x, y) the crop's top-left on the canvas, or None when there is nothing to draw."""
    if not overlay:
        return None
    img = np.zeros((GAME_H, GAME_W, 4), np.uint8)
    sx = lambda wx: (wx - scroll_x) * 4
    sy = lambda ly: (ly + 32) * 4                                      # level y has the 32 px status bar above it
    xs, ys = [], []                                                    # every point drawn, for the crop
    touch = lambda pts, pad=3: (xs.extend(q[0] + d for q in pts for d in (-pad, pad)),
                                ys.extend(q[1] + d for q in pts for d in (-pad, pad)))
    for it in sorted(overlay, key=lambda i: i.kind != "wedge"):        # cones first: they are a faint fill under the rest
        r, g, b = hex_rgb(it.colour)
        col, p = (r, g, b, 255), it.geometry
        if it.kind == "box":
            x, y, w, h = p
            c = [(sx(x), sy(y)), (sx(x + w), sy(y)), (sx(x + w), sy(y + h)), (sx(x), sy(y + h))]
            for i in range(4):
                _line(img, c[i], c[(i + 1) % 4], col, 3, it.line)
            touch(c)
        elif it.kind == "line":
            a, z = (sx(p[0]), sy(p[1])), (sx(p[2]), sy(p[3]))
            _line(img, a, z, col, 3, it.line)
            touch([a, z])
        elif it.kind == "dot":
            rad = max(2, int(round(p[2] * 4)))
            if it.anchor == "screen_right":                            # a direction marker, 22 px inside the edge, half transparent
                c = (GAME_W - 22, int(round(sy(p[1]))))
                cv2.circle(img, c, rad, (r, g, b, 128), -1, cv2.LINE_AA)
            else:
                c = (int(round(sx(p[0]))), int(round(sy(p[1]))))
                cv2.circle(img, c, rad, col, -1, cv2.LINE_AA)
            touch([c], rad + 2)
        elif it.kind == "wedge":                                       # the cone from Mario's eye to the box it measures
            ex, ey, x, y, w, h = p
            near = x if x >= ex else x + w
            eye, top, bot = (sx(ex), sy(ey)), (sx(near), sy(y)), (sx(near), sy(y + h))
            cv2.fillPoly(img, [np.array([eye, top, bot], np.int32)], (r, g, b, 18), cv2.LINE_AA)    # 7 % opaque, as in the video
            _line(img, eye, top, col, 1, it.line)
            _line(img, eye, bot, col, 1, it.line)
            touch([eye, top, bot])
    x0, x1 = max(0, int(min(xs))), min(GAME_W, int(max(xs)) + 1)
    y0, y1 = max(0, int(min(ys))), min(GAME_H, int(max(ys)) + 1)
    if x1 <= x0 or y1 <= y0:                                           # everything off screen
        return None
    return np.ascontiguousarray(img[y0:y1, x0:x1]), x0, y0


def png_bytes(img: np.ndarray) -> bytes:
    """An RGB(A) uint8 image as PNG bytes. Written by hand with no row filtering and fast deflate: OpenCV's encoder
    spends 27 ms on a mostly empty 1024 x 960 RGBA picture, this takes a fraction of that."""
    h, w, ch = img.shape
    raw = np.hstack([np.zeros((h, 1), np.uint8), np.ascontiguousarray(img).reshape(h, w * ch)]).tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (PNG_SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6 if ch == 4 else 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 1)) + chunk(b"IEND", b""))


class BrainLayer:
    """The brain panel of one run, rendered off the emulator's thread.

    A render takes ~50 ms (blurring a 896 x 1080 glow), far more than a frame, so it runs on its own thread at whatever
    rate it can sustain and the stream picks up the newest finished picture. The brightness scale is the run maximum
    SO FAR (the video knows the whole run's maximum in advance; a live run cannot)."""

    def __init__(self, run):
        self.data = source.brain_data(run, Path("<live>"))            # no rates.npz: the maxima are filled in as we go
        self.data.rate_max = {}
        self.panel = BrainPanel(self.data)
        self._hist: dict = {g: deque(maxlen=SMOOTH) for g in self.data.xyz}
        self._lock = threading.Lock()
        self._todo: Optional[tuple] = None
        self._done: Optional[tuple] = None                             # (frame, jpeg bytes)
        self._wake = threading.Event()
        self._stop = False
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()

    def submit(self, rates: dict, frame: int) -> None:
        """Feed one frame's group rates (call every frame: the smoothing and the maxima need them all)."""
        smooth = {}
        for g, v in rates.items():
            h = self._hist.setdefault(g, deque(maxlen=SMOOTH))
            h.append(v)
            smooth[g] = sum(h) / len(h)
            self.data.rate_max[g] = max(self.data.rate_max.get(g, 0.0), smooth[g])
        with self._lock:
            self._todo = (smooth, frame)
        self._wake.set()

    def latest(self, after: int = -1) -> Optional[tuple]:
        """(frame, jpeg bytes) of the newest finished picture, if it is newer than `after`."""
        with self._lock:
            return self._done if self._done and self._done[0] > after else None

    def _work(self) -> None:
        while not self._stop:
            self._wake.wait()
            self._wake.clear()
            with self._lock:
                job, self._todo = self._todo, None
            if job is None:
                continue
            rgb = self.panel.draw(*job)
            ok, buf = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            if ok:
                with self._lock:
                    self._done = (job[1], buf.tobytes())

    def close(self) -> None:
        self._stop = True
        self._wake.set()


def brain_map_png(fly) -> bytes:
    """The Fly page's mini brain map: the brain and nerve cord with every neuron group this fly uses lit at full strength
    (the panel of the live view without its text)."""
    data = source.brain_data(SimpleNamespace(fly=fly), Path("<map>"))
    data.rate_max = {g: 1.0 for g in data.xyz}
    rgb = BrainPanel(data).glow({g: 1.0 for g in data.xyz})
    return png_bytes(np.ascontiguousarray(rgb[:TEXT_Y - 8, COL_X - 30:COL_X + COL_W + 30]))
