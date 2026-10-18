"""R1 panels: BRAIN (left 576), MARIO (middle 768 x 720), DATA (right 576), title bar. Everything is drawn from the logs (a Log object); the emulator only supplies the NES frames.
One font (DejaVu Sans). Colour language (flyrun/SPEC.md): RED = looming, GREEN = hum / smell, WHITE = home, lavender = steering DNa / relays; teal = from the fly, orange = invented."""
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .. import c1_run as C
from ..brain import CACHE
from ..knobs import Knobs
from . import log as L

W, H, TITLE_H = 1920, 1080, 44
LW, MW, RW = 576, 768, 576
MX0, RX0 = LW, LW + MW
GAME_Y = TITLE_H + (H - TITLE_H - 720) // 2
BG = (14, 16, 22)
GREY = (84, 90, 104)
RED, GREEN, WHITE, NEUTRAL = (255, 72, 72), (64, 224, 96), (238, 238, 238), (170, 150, 255)
TEAL, ORANGE, DIM, TXT = (40, 200, 190), (255, 150, 40), (120, 126, 140), (214, 218, 228)
FONT = str(Path("C:/Windows/Fonts/DejaVuSans.ttf"))
_F = {}


def font(sz):
    if sz not in _F:
        _F[sz] = ImageFont.truetype(FONT, sz)
    return _F[sz]


# ------------------------------------------------------------------------------------------------ the run's log
class Log:
    def __init__(self, base, knobs=None):
        base = str(base)
        self.df = pd.read_csv(base + ".csv")
        self.h = np.load(base + ".npz")["h"].astype(np.float32)
        import json
        self.meta = json.load(open(base + ".json"))
        self.arm = self.meta["arm"]
        self.kn = knobs or replace(C.KN, **C.ARMS[self.arm])
        br = C._brain()
        self.brain = br
        self.n = br.K
        # shifted ("pre-step") columns: row k of the CSV is the state AFTER step k; the frame drawn at k is the state BEFORE it
        d = self.df
        self.feet_pre = d.feet_y.shift(1, fill_value=176).to_numpy()
        self.pow_pre = d.powerup.shift(1, fill_value=0).to_numpy()
        self.sl_pre = d.screen_left.shift(1, fill_value=0).to_numpy()
        # 3-frame smoothed rates
        cs = np.cumsum(np.vstack([np.zeros((1, self.n), np.float32), self.h]), axis=0)
        k = np.arange(len(self.h))
        lo = np.maximum(k - 2, 0)
        self.hs = (cs[k + 1] - cs[lo]) / (k + 1 - lo)[:, None]
        m = br.masks
        self.gf = self.h[:, m["DNp01"]].mean(1)
        self.dna_steer = d.steer.to_numpy()
        self.toggles = self.meta["toggles"]

    def __len__(self):
        return len(self.df)


# ------------------------------------------------------------------------------------------------ brain panel
GROUPS = [("LC4 / LPLC2 (looming)", RED), ("Giant Fiber DNp01", RED), ("TTMn", RED), ("hum: JO", GREEN), ("smell: ORN > PN > LAL030", GREEN), ("home: LC10a", WHITE), ("DNp09 (walk)", WHITE), ("DNa L / R (steer)", NEUTRAL)]


class BrainPanel:
    def __init__(self, log):
        self.log = log
        br = log.brain
        t = br.bodies.type.astype(str).to_numpy()
        side = br.bodies.somaSide.astype(str).to_numpy()
        ids = br.bodies.bodyId.to_numpy()
        aid, axyz = L.soma_all()
        x0, x1, z0, z1 = float(axyz[:, 0].min()), float(axyz[:, 0].max()), float(axyz[:, 2].min()), float(axyz[:, 2].max())
        self.s = (LW - 20) / (x1 - x0)
        self.ox, self.oy = 10, 140
        self.mid = (x0 + x1) / 2
        self.x0, self.x1, self.z0 = x0, x1, z0
        proj = lambda x, z: (self.ox + (x1 - x) * self.s, self.oy + (z - z0) * self.s)    # flipped x: fly's LEFT on the viewer's left, like the game's right
        # grey silhouette: density of all 141,781 somata
        hist = np.zeros((H, LW), np.float32)
        px, py = proj(axyz[:, 0].astype(np.float64), axyz[:, 2].astype(np.float64))
        np.add.at(hist, (np.clip(py.astype(int), 0, H - 1), np.clip(px.astype(int), 0, LW - 1)), 1.0)
        hist = cv2.GaussianBlur(hist, (0, 0), 1.1)
        v = np.clip(np.log1p(hist * 6) / np.log1p(hist.max() * 6 * 0.5), 0, 1)
        self.sil = (np.array(BG, np.float32)[None, None] + (np.array(GREY, np.float32) - np.array(BG, np.float32))[None, None] * v[..., None] * 1.0)
        # positions of the 881
        pos = pd.Series(range(len(aid)), index=aid)
        xy = np.zeros((self.log.n, 2))
        rng = np.random.default_rng(1)
        for i in range(self.log.n):
            if ids[i] in pos.index:
                x, _, z = axyz[pos[ids[i]]]
                xy[i] = proj(float(x), float(z))
            else:                                  # JO / ORN: no soma in the dataset (sensory neurons); schematic cluster above the brain, by side
                sgn = -1.0 if side[i] == "L" else 1.0
                jo = t[i].startswith("JO")
                cx = self.ox + (x1 - self.mid) * self.s + sgn * (0.13 if jo else 0.27) * (x1 - x0) * self.s
                xy[i] = (cx + rng.normal(0, 7), self.oy - (46 if jo else 26) + rng.normal(0, 6))
        self.xy = xy
        # drive colours
        col = np.tile(np.array(NEUTRAL, np.float32), (self.log.n, 1))
        orn_path = np.arange(self.log.n) >= 656
        loom = np.isin(t, ["LC4", "LPLC2", "DNp01", "TTMn"])
        hum = np.char.startswith(t.astype("U"), "JO")
        smell = orn_path | np.char.startswith(t.astype("U"), "ORN")
        home = np.isin(t, ["LC10a", "DNp09"])
        for m, c in ((loom, RED), (smell, GREEN), (hum, GREEN), (home, WHITE)):
            col[m] = c
        self.col = col
        self.rad = np.where(np.isin(t, ['DNp01', 'TTMn', 'DNp09', 'DNa01', 'DNa02']), 4, 2)
        self.groups = dict(loom=np.isin(t, ["LC4", "LPLC2"]), gf=t == "DNp01", ttmn=t == "TTMn", jo=hum, smell=smell & ~hum, home=t == "LC10a", dnp09=t == "DNp09", dna=np.isin(t, ["DNa01", "DNa02"]))
        # static layer: silhouette + key-group labels with leader lines
        img = Image.fromarray(np.clip(self.sil[:TITLE_H * 0 + H], 0, 255).astype(np.uint8)[:, :LW])
        dr = ImageDraw.Draw(img)
        labels = [("looming  LC4 / LPLC2", "loom", RED), ("Giant Fiber (DNp01)", "gf", RED), ("TTMn", "ttmn", RED), ("hum: JO (20)", "jo", GREEN),
                  ("smell: ORN > PN > LAL030", "smell", GREEN), ("home: LC10a", "home", WHITE), ("DNp09 walk", "dnp09", WHITE), ("DNa steer", "dna", NEUTRAL)]
        placed = []
        for name, g, c in sorted(labels, key=lambda a: self.xy[self.groups[a[1]]].mean(0)[1]):
            cx, cy = self.xy[self.groups[g]].mean(0)
            right = cx > LW / 2
            ty = cy
            for py_ in placed:
                if abs(ty - py_) < 25:
                    ty = py_ + 25
            placed.append(ty)
            tw = dr.textlength(name, font=font(13))
            tx = LW - 8 - tw if right else 8
            ex = tx - 4 if right else tx + tw + 4
            dr.line([(ex, ty + 8), (cx, cy)], fill=tuple(int(v * 0.55) for v in c), width=1)
            dr.text((tx, ty), name, font=font(13), fill=c)
        dr.text((10, 52), "BRAIN  881 real neurons (MaleCNS v1.0)", font=font(15), fill=TXT)
        dr.text((10, 74), "grey: all 141,781 somata   bright: the 881 (rate, 3-frame mean)", font=font(11), fill=DIM)
        dr.text((10, H - 24), "JO / ORN have no soma in the dataset: drawn as schematic clusters above the head", font=font(10), fill=DIM)
        self.static = np.asarray(img).astype(np.float32)
        self.gf_pulse = self.dna_pulse = -99
        self.ring_gf, self.ring_dna = [], []

    def centre(self, g):
        return self.xy[self.groups[g]].mean(0)

    def draw(self, k):
        lg = self.log
        r = lg.hs[k]
        b = np.clip(r / 3.0, 0, 1) ** 0.6
        b = 0.20 + 0.80 * b
        layer = np.zeros((H, LW, 3), np.float32)
        for i in np.argsort(b):
            cv2.circle(layer, (int(self.xy[i, 0]), int(self.xy[i, 1])), self.rad[i] if b[i] < 0.5 else self.rad[i] + 1, tuple(float(v) * b[i] for v in self.col[i]), -1, cv2.LINE_AA)
        glow = cv2.GaussianBlur(layer, (0, 0), 5) * 1.6
        out = self.static + layer + glow
        # ring flashes: the Giant Fiber when it fires (DNp01 rate crosses 0.25 upward), the DNa when it turns (steer < -0.01 = Left)
        gf = lg.gf
        if k > 0 and gf[k] >= 0.25 > gf[k - 1]:
            self.ring_gf.append(k)
        st = lg.dna_steer
        if k > 0 and st[k] < -0.01 <= st[k - 1]:
            self.ring_dna.append(k)
        for lst, g, c in ((self.ring_gf, "gf", RED), (self.ring_dna, "dna", NEUTRAL)):
            cx, cy = self.centre(g)
            for k0 in lst[-4:]:
                age = k - k0
                if 0 <= age < 24:
                    a = 1 - age / 24
                    cv2.circle(out, (int(cx), int(cy)), int(8 + age * 1.6), tuple(float(v) * a for v in c), 2, cv2.LINE_AA)
        return np.clip(out, 0, 255).astype(np.uint8)


# ------------------------------------------------------------------------------------------------ game panel
def parse_box(s):
    if not isinstance(s, str) or not s:
        return None
    return tuple(int(v) for v in s.split())


def game_panel(frame, log, k):
    img = cv2.resize(np.ascontiguousarray(frame), None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST).copy()
    r = log.df.iloc[k]
    sl = float(log.sl_pre[k])
    sx = lambda wx: int(round((wx - sl) * 3))
    sy = lambda ty: int(round((ty + 32) * 3))
    box = parse_box(r.box_x_top_w_h)
    if box and r.threat != "none":
        bx, top, bw, bh = box
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 3, cv2.LINE_AA)
    base = parse_box(r.pit_base_x_top_w_h)
    if base:
        bx, top, bw, bh = base
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 1, cv2.LINE_AA)
    if r.hum_level > 0 and not pd.isna(r.hum_block_x):
        bx, bottom = r.hum_block_x, r.hum_bottom
        cv2.line(img, (sx(bx), sy(bottom) + 5), (sx(bx + 16), sy(bottom) + 5), GREEN, 4, cv2.LINE_AA)
    if not pd.isna(r.smell_x):
        bx, top = r.smell_x, r.smell_top
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + 16), sy(top + 16)), GREEN, 3, cv2.LINE_AA)
    if log.toggles["home"]:
        eye = log.feet_pre[k] - (24 if log.pow_pre[k] >= 1 else 16)
        a = min(1.0, log.kn.HOME_R)
        ov = img.copy()
        cv2.circle(ov, (img.shape[1] - 22, sy(eye)), int(5 + 30 * log.kn.HOME_R), WHITE, -1, cv2.LINE_AA)
        img = cv2.addWeighted(ov, a, img, 1 - a, 0)
    return img


# ------------------------------------------------------------------------------------------------ data panel
SPAN = 180
TRACES = [("theta of the chosen threat", "deg", 0, 180, RED), ("hum level (JO input)", "", 0, 10, GREEN), ("smell L / R (ORN input)", "", 0, 80, GREEN),
          ("TTMn (jump motor neuron)", "", 0, 0.6, RED), ("steer = DNa R - L", "", -0.06, 0.06, NEUTRAL)]


class DataPanel:
    def __init__(self, log):
        self.log = log
        d = log.df
        self.series = [np.degrees(d.theta.to_numpy()), d.hum_level.fillna(0).to_numpy(), (d.smell_L.fillna(0).to_numpy(), d.smell_R.fillna(0).to_numpy()), d.ttmn.to_numpy(), d.steer.to_numpy()]
        self.y0 = TITLE_H + 94
        self.th = 108
        self.gap = 22
        kn = log.kn
        self.press, self.release = kn.TTMN_THRESH, (kn.RELEASE_THRESH if kn.RELEASE_THRESH is not None else kn.TTMN_THRESH)
        # static layer
        img = Image.new("RGB", (RW, H), BG)
        dr = ImageDraw.Draw(img)
        dr.text((10, 52), "DATA  (last 3 s)", font=font(15), fill=TXT)
        names = [("looming", "looming" if True else "", "looming"), ("home", "", "home"), ("hum", "", "hum"), ("smell", "", "smell")]
        x = 10
        tg = log.toggles
        for nm, key in (("looming", "looming_enemy"), ("home", "home"), ("hum", "hum"), ("smell", "smell")):
            on = bool(tg[key])
            c = {"looming": RED, "home": WHITE, "hum": GREEN, "smell": GREEN}[nm]
            w = int(dr.textlength(nm + (' ON' if on else ''), font=font(14))) + 26
            dr.rounded_rectangle([x, 74, x + w, 98], 12, outline=c if on else (60, 64, 74), fill=tuple(int(v * 0.30) for v in c) if on else None, width=2)
            dr.text((x + 13, 77), nm + (" ON" if on else ""), font=font(14), fill=c if on else (90, 94, 104))
            x += w + 10
        for i, (name, unit, lo, hi, c) in enumerate(TRACES):
            y = self.y0 + i * (self.th + self.gap) + 14
            dr.text((10, y - 17), name, font=font(12), fill=c)
            dr.rectangle([10, y, RW - 10, y + self.th], outline=(46, 50, 60))
            if i == 3:
                for v, nm in ((self.press, "press"), (self.release, "release")):
                    yy = y + self.th - (v - lo) / (hi - lo) * self.th
                    dr.line([(10, yy), (RW - 10, yy)], fill=(120, 120, 60) if nm == "press" else (90, 90, 90), width=1)
                lab = f"press = release {self.press:.2f}" if self.press == self.release else f"press {self.press:.2f}  release {self.release:.2f}"
                dr.text((RW - 12 - dr.textlength(lab, font=font(10)), y + 2), lab, font=font(10), fill=(170, 170, 90))
            if i == 4:
                for v in (-0.01, 0.01):
                    yy = y + self.th - (v - lo) / (hi - lo) * self.th
                    dr.line([(10, yy), (RW - 10, yy)], fill=(120, 90, 60), width=1)
                dr.text((RW - 60, y + 2), "+0.01", font=font(10), fill=(170, 130, 80))
                dr.text((RW - 60, y + self.th - 14), "-0.01 L", font=font(10), fill=(170, 130, 80))
        self.static = np.asarray(img)
        # knob panel (static): values and who set them
        self.knob_y = self.y0 + 5 * (self.th + self.gap) + 6
        S = self.static.copy()
        im2 = Image.fromarray(S)
        dr = ImageDraw.Draw(im2)
        y = self.knob_y + 78
        W_ = log.brain.W
        dr.text((10, y), "teal = from the fly    orange = invented", font=font(11), fill=DIM)
        y += 16
        dr.text((10, y), "wiring", font=font(11), fill=TEAL)
        dr.text((64, y), f"MaleCNS v1.0 · {log.n} neurons · {int((W_ != 0).sum()):,} synapse pairs · cell types", font=font(11), fill=TXT)
        y += 15
        kv = [("HOME_R", f"{kn.HOME_R}"), ("G", f"{kn.G}"), ("ALPHA", f"{kn.ALPHA}"), ("CLIP", f"{kn.CLIP:g}"), ("SUBSTEPS", f"{kn.SUBSTEPS}"), ("TTMN_THRESH", f"{kn.TTMN_THRESH}"),
              ("DNP09_THRESH", f"{kn.DNP09_THRESH}"), ("STEER_THRESH", f"{kn.STEER_THRESH}"), ("HUM_GAIN", f"{kn.HUM_GAIN}"), ("SMELL_GAIN", f"{kn.SMELL_GAIN}"), ("SENSOR_NOISE", f"{log.meta['episode']['sigma']}"), ("MARIO_BOX", "12x16 / 12x24")]
        for j, (a, b) in enumerate(kv):
            cx = 10 + (j % 2) * 280
            cy = y + (j // 2) * 15
            dr.text((cx, cy), "●", font=font(10), fill=ORANGE)
            dr.text((cx + 14, cy), f"{a} {b}", font=font(11), fill=TXT)
        self.static = np.asarray(im2)

    def draw(self, k):
        lg = self.log
        img = self.static.copy()
        lo_k = max(0, k - SPAN + 1)
        xs = np.arange(lo_k, k + 1)
        for i, (name, unit, lo, hi, c) in enumerate(TRACES):
            y = self.y0 + i * (self.th + self.gap) + 14
            ser = self.series[i] if i != 2 else self.series[2]
            lines = [(ser, c)] if i != 2 else [(ser[0], (120, 255, 150)), (ser[1], (30, 160, 70))]
            for s, col in lines:
                v = np.clip(s[lo_k:k + 1], lo, hi)
                px = 10 + (xs - (k - SPAN + 1)) / (SPAN - 1) * (RW - 20)
                py = y + self.th - (v - lo) / (hi - lo) * self.th
                pts = np.stack([px, py], 1).astype(np.int32).reshape(-1, 1, 2)
                if len(pts) > 1:
                    cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
        pil = Image.fromarray(img)
        dr = ImageDraw.Draw(pil)
        d = lg.df.iloc[k]
        vals = [f"{np.degrees(d.theta):5.1f}", f"{d.hum_level if not pd.isna(d.hum_level) else 0:4.1f}", f"L {d.smell_L:4.1f}  R {d.smell_R:4.1f}", f"{d.ttmn:.3f}", f"{d.steer:+.4f}"]
        for i, v in enumerate(vals):
            y = self.y0 + i * (self.th + self.gap) + 14
            dr.text((RW - 12 - dr.textlength(v, font=font(12)), y - 17), v, font=font(12), fill=TXT)
        # buttons, position, score, power
        by = self.knob_y
        keys = [("←", bool(d.left)), ("→", bool(d.right)), ("A", bool(d.a))]
        for j, (nm, on) in enumerate(keys):
            x = 10 + j * 56
            dr.rounded_rectangle([x, by, x + 48, by + 44], 8, fill=(236, 236, 240) if on else (30, 34, 44), outline=(110, 116, 130), width=2)
            dr.text((x + 24 - dr.textlength(nm, font=font(22)) / 2, by + 6), nm, font=font(22), fill=(20, 22, 30) if on else (96, 100, 112))
        pw = "big" if d.powerup >= 1 else "small"
        dr.text((190, by), f"x {int(d.x)}", font=font(16), fill=TXT)
        dr.text((190, by + 22), f"score {int(d.score)}", font=font(16), fill=TXT)
        dr.text((340, by), f"power {pw}", font=font(16), fill=TXT)
        dr.text((340, by + 22), f"? blocks hit {int(d.blocks_hit)}", font=font(16), fill=TXT)
        return np.asarray(pil)


# ------------------------------------------------------------------------------------------------ the whole frame
class Renderer:
    def __init__(self, log, label=None):
        self.log = log
        self.brain, self.data = BrainPanel(log), DataPanel(log)
        self.label = label or f"arm {log.arm}"
        tg = log.toggles
        self.legend = self._static_mid()

    def _static_mid(self):
        img = Image.new("RGB", (MW, H - TITLE_H - 720 - (GAME_Y - TITLE_H) + (GAME_Y - TITLE_H)), BG)
        return img

    def frame(self, nes_frame, k):
        lg = self.log
        out = np.zeros((H, W, 3), np.uint8)
        out[:] = BG
        out[:, :LW] = self.brain.draw(k)[:H]
        out[:, RX0:] = self.data.draw(k)[:H]
        out[GAME_Y:GAME_Y + 720, MX0:MX0 + MW] = game_panel(nes_frame, lg, k)
        pil = Image.fromarray(out)
        dr = ImageDraw.Draw(pil)
        dr.rectangle([0, 0, W, TITLE_H], fill=(22, 25, 34))
        dr.text((16, 10), "MaleCNS fruit-fly brain plays Super Mario Bros 1-1", font=font(20), fill=TXT)
        right = f"{self.label}     frame {k}"
        dr.text((W - 16 - dr.textlength(right, font=font(18)), 12), right, font=font(18), fill=(190, 196, 210))
        ly = GAME_Y + 720 + 22
        x = MX0 + 24
        for nm, c in (("looming", RED), ("hum / smell", GREEN), ("home", WHITE)):
            dr.rectangle([x, ly + 4, x + 18, ly + 22], fill=c)
            dr.text((x + 26, ly), nm, font=font(15), fill=TXT)
            x += 36 + int(dr.textlength(nm, font=font(15))) + 40
        dr.text((MX0 + 24, ly + 30), "the game, seen as the fly's senses read it from RAM", font=font(12), fill=DIM)
        for xx in (LW, RX0):
            dr.line([(xx, TITLE_H), (xx, H)], fill=(40, 44, 54), width=1)
        return np.asarray(pil)
