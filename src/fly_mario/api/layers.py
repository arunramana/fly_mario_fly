"""The picture of a live run, as separate layers the browser stacks: the brain panel (JPEG) and the game screen (PNG,
256 x 240, drawn at x4 by the page). The sense overlay is not a picture: its items go out as JSON and the page draws
them (web/src/components/overlayDraw.ts, the same geometry as render.draw.game_panel). Keeping the layers apart is what
lets "Show senses" and "Show brain" toggle instantly in the browser.

The brain panel is render.draw.BrainPanel (the approved R3 look).
Talks to the runner and render only; names no sense or object.
"""
from __future__ import annotations

import struct
import threading
import time
import zlib
from types import SimpleNamespace
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from fly_mario.render import source
from fly_mario.render.draw import COL_W, COL_X, TEXT_Y, BrainPanel

SMOOTH = 3                     # the glow and the index use a 3-frame mean of the rates (render.source.SMOOTH)
JPEG_QUALITY = 82
PANEL_FPS = 12                 # the brain panel is redrawn at most this often; the rates still feed the smoothing every frame
PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


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

    A render takes ~30 ms, far more than a frame, so it runs on its own thread, at most PANEL_FPS times a
    second, and the stream picks up the newest finished picture. The brightness scale is the run maximum SO FAR (the video knows the whole run's maximum in advance; a live run cannot)."""

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
        last = 0.0
        while not self._stop:
            self._wake.wait()
            self._wake.clear()
            wait = last + 1.0 / PANEL_FPS - time.perf_counter()
            if wait > 0 and not self._stop:
                time.sleep(wait)                                       # the newest rates are picked up after the pause
            last = time.perf_counter()
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
