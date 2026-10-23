"""The two-panel frame (1920 x 1080, black): LEFT = glowing-somata brain + nerve cord + title + index, RIGHT = the game at NES x4 with the sense overlay.

Ported from the approved R3 / R3b renderer. Brain geometry: every soma projected x against z (flipped, so the fly's left is on the viewer's left),
the nerve cord (somata below Z_SPLIT in the data's gap) at its own smaller scale underneath. Dim grey points = every MaleCNS soma; circuit neurons
glow in their group colour with brightness = group rate / the group's run maximum.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from fly_mario.render import palette as P
from fly_mario.render.data import BrainData, FrameData

W, H = 1920, 1080
LEFT_W, COL_W, COL_X = 896, 640, 128                 # the left panel and its centred content column
GAME_W, GAME_H, GAME_Y = 1024, 960, 60               # NES 256 x 240 at x4
GAME_X = LEFT_W                                      # right-aligned when the brain is shown, centred when not
BRAIN_Y0 = 22                                        # top of the brain
VNC_Y0, VNC_H = 300, 262                             # the nerve cord, at its own scale so everything fits above the text
Z_SPLIT = 52000.0                                    # somata with z above this are nerve cord (the data has a gap there)
TEXT_Y = 574
INDEX_Y, INDEX_DY = 746, 27
FONT, FONT_B = "C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"
# The somata and their halo (blur sigma 2.5 -> ~10 px) lie inside this box of the left panel: (y0, y1, x0, x1).
GLOW_BOX = (0, TEXT_Y + 8, COL_X - 24, COL_X + COL_W + 24)
FLOOR = 0.02                                         # brightness floor: a ~1e-3 baseline must not look lit


@lru_cache(maxsize=None)
def font(sz: int, bold: bool = False):
    return ImageFont.truetype(FONT_B if bold else FONT, sz)


def hex_rgb(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------------------------- the brain panel
def _grey(dens):
    """Log-density-free R3b tone: each soma is one 1-px point worth 15 grey levels, capped at 70, so the cloud reads as fine points."""
    v = np.clip(dens * 15.0, 0, 70)
    out = np.zeros(dens.shape + (3,), np.float32)
    for c, base in enumerate((70, 78, 74)):
        out[..., c] = np.maximum(v * base / 70.0, P.BG[c])
    return out


class BrainPanel:
    def __init__(self, brain: BrainData):
        self.b = brain
        a = brain.all_xyz.astype(np.float64)
        x0, x1, z0 = a[:, 0].min(), a[:, 0].max(), a[:, 2].min()
        vn = a[:, 2] >= Z_SPLIT
        vx0, vx1, vz0, vz1 = a[vn, 0].min(), a[vn, 0].max(), a[vn, 2].min(), a[vn, 2].max()
        s, sv = (COL_W - 12) / (x1 - x0), VNC_H / (vz1 - vz0)
        self._brain = lambda x, z: (COL_X + 6 + (x1 - x) * s, BRAIN_Y0 + (z - z0) * s)
        self._cord = lambda x, z: (COL_X + COL_W / 2 + ((vx0 + vx1) / 2 - x) * sv, VNC_Y0 + (z - vz0) * sv)
        dens_b, dens_v = np.zeros((H, LEFT_W), np.float32), np.zeros((H, LEFT_W), np.float32)
        px, py = self._brain(a[~vn, 0], a[~vn, 2])
        np.add.at(dens_b, (py.astype(int), px.astype(int)), 1.0)
        px, py = self._cord(a[vn, 0], a[vn, 2])
        np.add.at(dens_v, (py.astype(int), px.astype(int)), 1.0)
        self.bg = np.maximum(_grey(dens_b), _grey(dens_v))
        self._bg_u8 = np.clip(self.bg, 0, 255).astype(np.uint8)     # the cached background: everything outside GLOW_BOX
        self.px = {g: self._project(v) for g, v in brain.xyz.items()}
        self.other = self._project(brain.other_xyz)
        self.rows = [(lab, role, [g for g in gs if g in brain.xyz]) for lab, role, gs in brain.index]
        self.rows = [r for r in self.rows if r[2]]
        self.has_terminals = any(g in brain.xyz for g in brain.placed_by_terminal)

    def _project(self, xyz) -> np.ndarray:
        xyz = np.asarray(xyz, dtype=np.float64).reshape(-1, 3)
        out = np.zeros((len(xyz), 2))
        for i, (x, _, z) in enumerate(xyz):
            if np.isnan(x):
                out[i] = (-100, -100)
            else:
                out[i] = (self._cord if z >= Z_SPLIT else self._brain)(x, z)
        return np.round(out).astype(int)

    def level(self, rates: dict, g: str) -> float:
        """Brightness 0..1 of a group: its rate against its own run maximum (floored)."""
        return float(np.clip(rates.get(g, 0.0) / max(self.b.rate_max.get(g, 0.0), FLOOR), 0, 1))

    def glow(self, rates: dict) -> np.ndarray:
        """The panel with the somata glowing. Only the box around the brain and the cord (+ halo margin) is drawn and blurred;
        the rest of the panel is the cached background, so the result is the same as blurring the whole panel."""
        y0, y1, x0, x1 = GLOW_BOX
        layer = np.zeros((y1 - y0, x1 - x0, 3), np.float32)
        for x, y in self.other:                                        # relays: faint, constant
            cv2.circle(layer, (int(x) - x0, int(y) - y0), 1, tuple(0.28 * c for c in self.b.other_colour), -1, cv2.LINE_AA)
        for g, pts in self.px.items():
            a = self.level(rates, g) ** 0.7
            bright = 0.28 + 0.72 * a
            col = tuple(float(c) * bright for c in self.b.colours[g])
            r = max(1, int(round((1.8 if g in self.b.big else 1.0) * (1 + 0.5 * a))))
            for x, y in pts:
                cv2.circle(layer, (int(x) - x0, int(y) - y0), r, col, -1, cv2.LINE_AA)
        out = self._bg_u8.copy()
        out[y0:y1, x0:x1] = np.clip(self.bg[y0:y1, x0:x1] + layer + cv2.GaussianBlur(layer, (0, 0), 2.5) * 1.2,   # additive core + soft halo
                                    0, 255).astype(np.uint8)
        return out

    def draw(self, rates: dict, frame: int) -> np.ndarray:
        pil = Image.fromarray(self.glow(rates))
        dr = ImageDraw.Draw(pil)
        x, y = COL_X, TEXT_Y
        dr.text((x, y), "LIVE BRAIN", font=font(22, True), fill=(255, 255, 255))
        dr.text((x + COL_W, y + 4), f"frame {frame}", font=font(16), fill=P.DIM, anchor="ra")
        dr.text((x, y + 34), f"{self.b.n_neurons} neurons at their real somas  ·  MaleCNS v1.0", font=font(16), fill=P.TXT)
        dr.text((x, y + 58), "brightness = activity", font=font(16), fill=P.DIM)
        if self.has_terminals:
            dr.text((x, y + 80), "JO/ORN at their brain terminals (cell bodies in the antenna)", font=font(16), fill=P.DIM)
        yy = INDEX_Y
        for label, role, groups in self.rows:
            n = np.array([self.b.counts.get(g, 1) for g in groups], float)
            val = float(np.dot([rates.get(g, 0.0) for g in groups], n) / n.sum())
            gmax = float(np.dot([self.b.rate_max.get(g, 0.0) for g in groups], n) / n.sum())
            a = float(np.clip(val / max(gmax, 1e-9), 0, 1))
            f = 1.0 if gmax > FLOOR else 0.28                          # a group that never fires in this run is dimmed
            col = tuple(int(v * f) for v in self.b.colours[groups[0]])
            tc = tuple(int(v * f) for v in P.TXT)
            dr.ellipse([x, yy + 5, x + 12, yy + 17], fill=col)
            dr.text((x + 24, yy), label, font=font(18, True), fill=tc)
            dr.text((x + 108, yy), role, font=font(18), fill=tc)
            dr.rectangle([x + 330, yy + 5, x + 450, yy + 17], outline=(52, 52, 50))
            if a > 0:
                dr.rectangle([x + 330, yy + 5, x + 330 + int(120 * a), yy + 17], fill=col)
            dr.text((x + COL_W, yy), f"{val:7.3f}", font=font(18), fill=tc, anchor="ra")
            yy += INDEX_DY
        return np.asarray(pil)


# ---------------------------------------------------------------------------------------------- the game panel
def _segments(p0, p1, style):
    """Split a line into (start, end) pieces for a dashed / dotted style (screen pixels)."""
    on, off = {"dashed": (14, 9), "dotted": (3, 7)}[style]
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    length = float(np.hypot(*(p1 - p0)))
    if length == 0:
        return []
    u, t = (p1 - p0) / length, 0.0
    out = []
    while t < length:
        out.append((p0 + u * t, p0 + u * min(t + on, length)))
        t += on + off
    return out


def _line(img, p0, p1, col, width, style):
    if style == "solid":
        cv2.line(img, tuple(int(round(v)) for v in p0), tuple(int(round(v)) for v in p1), col, width, cv2.LINE_AA)
        return
    for a, b in _segments(p0, p1, style):
        cv2.line(img, tuple(int(round(v)) for v in a), tuple(int(round(v)) for v in b), col, width, cv2.LINE_AA)


def game_panel(game: np.ndarray, overlay: list, scroll_x: float, show_senses: bool = True, scale: int = 4) -> np.ndarray:
    """NES x`scale` (x4 = 1024 x 960 by default). With show_senses False the result is the plain upscaled game, pixel for pixel."""
    k = scale
    img = cv2.resize(np.ascontiguousarray(game), None, fx=k, fy=k, interpolation=cv2.INTER_NEAREST)
    if not show_senses or not overlay:
        return img
    img = img.copy()
    sx = lambda wx: (wx - scroll_x) * k
    sy = lambda ly: (ly + 32) * k                                      # level y has the 32 px status bar above it
    lw = 3 if k >= 4 else 2
    for it in overlay:
        col, g = hex_rgb(it.colour), it.geometry
        if it.kind == "box":
            x, y, w, h = g
            c = [(sx(x), sy(y)), (sx(x + w), sy(y)), (sx(x + w), sy(y + h)), (sx(x), sy(y + h))]
            for i in range(4):
                _line(img, c[i], c[(i + 1) % 4], col, lw, it.line)
        elif it.kind == "line":
            x0, y0, x1, y1 = g
            _line(img, (sx(x0), sy(y0)), (sx(x1), sy(y1)), col, lw, it.line)
        elif it.kind == "dot":
            x, y, r = g
            if it.anchor == "screen_right":                            # a direction marker, 22 px inside the edge, half transparent (as R3)
                ov = img.copy()
                cv2.circle(ov, (256 * k - 22, int(round(sy(y)))), max(2, int(round(r * k))), col, -1, cv2.LINE_AA)
                img = cv2.addWeighted(ov, 0.5, img, 0.5, 0)
            else:
                cv2.circle(img, (int(round(sx(x))), int(round(sy(y)))), max(2, int(round(r * k))), col, -1, cv2.LINE_AA)
        elif it.kind == "wedge":                                       # the cone from Mario's eye to the box it measures
            ex, ey, x, y, w, h = g
            near = x if x >= ex else x + w
            eye, top, bot = (sx(ex), sy(ey)), (sx(near), sy(y)), (sx(near), sy(y + h))
            ov = img.copy()
            cv2.fillPoly(ov, [np.array([eye, top, bot], np.int32)], col, cv2.LINE_AA)
            img = cv2.addWeighted(ov, 0.07, img, 0.93, 0)
            _line(img, eye, top, col, 1, it.line)
            _line(img, eye, bot, col, 1, it.line)
    return img


# ---------------------------------------------------------------------------------------------- the whole frame
class Renderer:
    def __init__(self, brain: BrainData | None, show_senses: bool = True, show_brain: bool = True):
        self.show_senses = show_senses
        self.show_brain = show_brain and brain is not None
        self.panel = BrainPanel(brain) if self.show_brain else None

    def frame(self, fd: FrameData) -> np.ndarray:
        out = np.zeros((H, W, 3), np.uint8)
        out[:] = P.BG
        gx = GAME_X if self.show_brain else (W - GAME_W) // 2
        if self.show_brain:
            out[:, :LEFT_W] = self.panel.draw(fd.rates, fd.frame)
        out[GAME_Y:GAME_Y + GAME_H, gx:gx + GAME_W] = game_panel(fd.game, fd.overlay, fd.scroll_x, self.show_senses)
        return out
