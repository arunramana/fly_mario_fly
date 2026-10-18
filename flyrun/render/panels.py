"""R2 layout v3 (1920 x 1080): top bar 60 | BRAIN map 544 x 960 | GAME 1024 x 960 (NES x4) | DATA 352 x 960 | callout bar 60. Everything is drawn from the logs (a Log object); the emulator only supplies
the NES frames. One font family (DejaVu Sans): >= 22 px for the data column, callouts and title card, 18 px for brain labels. Colour language (flyrun/SPEC.md): red = looming, green = hum / smell,
white = home, violet = steering (DNa); teal = from the fly, orange = invented (title card only)."""
from dataclasses import replace
from itertools import permutations
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .. import c1_run as C
from . import log as L

W, H = 1920, 1080
TOP, BOT = 60, 60
PH = H - TOP - BOT                                  # panel height 960
LW, MW, RW = 544, 1024, 352
MX0, RX0 = LW, LW + MW
BG = (4, 5, 8)
RED, GREEN, WHITE, VIOLET = (255, 72, 72), (64, 224, 96), (240, 240, 240), (176, 140, 255)
TEAL, ORANGE, DIM, TXT = (40, 200, 190), (255, 150, 40), (120, 126, 140), (222, 226, 236)
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
        d = self.df
        # row k of the CSV is the state AFTER step k; the frame drawn at k is the state BEFORE it
        self.feet_pre = d.feet_y.shift(1, fill_value=176).to_numpy()
        self.pow_pre = d.powerup.shift(1, fill_value=0).to_numpy()
        self.sl_pre = d.screen_left.shift(1, fill_value=0).to_numpy()
        cs = np.cumsum(np.vstack([np.zeros((1, self.n), np.float32), self.h]), axis=0)      # 3-frame smoothed rates
        k = np.arange(len(self.h))
        lo = np.maximum(k - 2, 0)
        self.hs = (cs[k + 1] - cs[lo]) / (k + 1 - lo)[:, None]
        self.gf = self.h[:, br.masks["DNp01"]].mean(1)
        self.dna_steer = d.steer.to_numpy()
        # "the Giant Fiber fires": DNp01 crosses 0.25 upward, or a grounded A press starts (the jump itself); events within 10 frames of an earlier one are merged
        up = np.flatnonzero((self.gf[1:] >= 0.25) & (self.gf[:-1] < 0.25)) + 1
        on = d.index[(d.a == 1) & (d.a.shift(1, fill_value=0) == 0) & (d.airborne == 0)].to_numpy()
        self.fire = []
        for f in sorted(set(up.tolist()) | set(on.tolist())):
            if not self.fire or f - self.fire[-1] > 10:
                self.fire.append(int(f))
        self.fire_set = set(self.fire)
        self.toggles = self.meta["toggles"]
        self.events = self._events()

    def _events(self):
        """[(frame, text, colour)] for the callout line."""
        d, ev = self.df, []
        for f in self.fire:
            th = float(np.degrees(d.theta[f:f + 4].max()))
            ev.append((f, f"Giant Fiber fires · θ {th:.0f}°" if th > 0.5 else "Giant Fiber fires", RED))
        hum = d.hum_level.fillna(0).to_numpy() > 0
        for f in np.flatnonzero(hum[1:] & ~hum[:-1]) + 1:
            ev.append((int(f), "? block hums", GREEN))
        sm = (d.smell_L.fillna(0) > 0) | (d.smell_R.fillna(0) > 0)
        for f in np.flatnonzero((sm.to_numpy()[1:]) & ~(sm.to_numpy()[:-1])) + 1:
            ev.append((int(f), "mushroom smells sweet", GREEN))
        lon = (d.left == 1) & (d.left.shift(1, fill_value=0) == 0)
        for f in d.index[lon & sm]:
            ev.append((int(f), "smell pulls left", GREEN))
        for f in np.flatnonzero(np.diff(d.blocks_hit.to_numpy()) > 0) + 1:
            ev.append((int(f), "? block hit", WHITE))
        for f in np.flatnonzero(np.diff(d.powerup.to_numpy()) > 0) + 1:
            ev.append((int(f), "mushroom eaten", GREEN))
        if int(self.meta["summary"].get("flag_get", 0)):
            ev.append((len(d) - 1, "flag reached", WHITE))
        return sorted(ev)

    def callout(self, k):
        """-> (text, colour, alpha) of the latest event within 90 frames (1.5 s), fading over the last 40 frames; None if none."""
        cur = [e for e in self.events if 0 <= k - e[0] < 90]
        if not cur:
            return None
        f, text, col = cur[-1]
        age = k - f
        return text, col, 1.0 if age < 50 else 1 - (age - 50) / 40

    def __len__(self):
        return len(self.df)


# ------------------------------------------------------------------------------------------------ icons (drive on / off)
def icon(dr, cx, cy, s, kind, on):
    """The four drive icons: looming = growing red box, hum = '?' block with a green line under it, smell = green box, home = white dot. Dim grey when off."""
    c = {"looming": RED, "hum": GREEN, "smell": GREEN, "home": WHITE}[kind] if on else (70, 74, 84)
    w = max(2, s // 14)
    h = s // 2
    if kind == "looming":
        dr.rectangle([cx - h // 2, cy - h // 2, cx + h // 2, cy + h // 2], outline=c, width=w)
        dr.rectangle([cx - h, cy - h, cx + h, cy + h], outline=c, width=w)
    elif kind == "hum":
        dr.rectangle([cx - h * 0.6, cy - h, cx + h * 0.6, cy + h * 0.2], outline=c, width=w)
        dr.text((cx, cy - h * 0.4), "?", font=font(max(12, s // 2)), fill=c, anchor="mm")
        dr.line([(cx - h * 0.8, cy + h * 0.6), (cx + h * 0.8, cy + h * 0.6)], fill=c, width=w + 2)
    elif kind == "smell":
        dr.rectangle([cx - h * 0.7, cy - h * 0.7, cx + h * 0.7, cy + h * 0.7], outline=c, width=w + 1)
    else:
        dr.ellipse([cx - h * 0.7, cy - h * 0.7, cx + h * 0.7, cy + h * 0.7], fill=c)


# ------------------------------------------------------------------------------------------------ brain panel
# The WHOLE brain and nerve cord, scaled to the panel width (margins 24 px, so the brain fills 91% of the width); nothing clipped. Panel-local coordinates.
MARGIN = 24
BRAIN_OY = 150                                  # panel y of the top of the brain (room above for the JO / ORN schematic clusters and the top label)


def seg_cross(p, q, r, s):
    d = lambda a, b, c: (c[0] - a[0]) * (b[1] - a[1]) - (b[0] - a[0]) * (c[1] - a[1])
    return d(p, q, r) * d(p, q, s) < 0 and d(r, s, p) * d(r, s, q) < 0


def seg_hits_rect(p, q, rect):
    x0, y0, x1, y1 = rect
    return any(x0 <= p[0] + (q[0] - p[0]) * t / 40 <= x1 and y0 <= p[1] + (q[1] - p[1]) * t / 40 <= y1 for t in range(41))


class BrainPanel:
    def __init__(self, log):
        self.log = log
        br = log.brain
        t = br.bodies.type.astype(str).to_numpy()
        side = br.bodies.somaSide.astype(str).to_numpy()
        ids = br.bodies.bodyId.to_numpy()
        aid, axyz = L.soma_all()
        axyz = axyz.astype(np.float64)
        x0, x1, z0 = axyz[:, 0].min(), axyz[:, 0].max(), axyz[:, 2].min()
        self.s = (LW - 2 * MARGIN) / (x1 - x0)
        self.z0 = z0
        proj = lambda x, z: (MARGIN + (x1 - x) * self.s, BRAIN_OY + (z - z0) * self.s)       # flipped x: the fly's LEFT on the viewer's left, like the game's right
        self.bottom = BRAIN_OY + (axyz[:, 2].max() - z0) * self.s
        # every soma is a tiny dim point (additive counts, no blur)
        hist = np.zeros((H, LW), np.float32)
        px, py = proj(axyz[:, 0], axyz[:, 2])
        np.add.at(hist, (py.astype(int), px.astype(int)), 1.0)
        v = (1 - np.exp(-hist * 0.45)) * 0.62
        sil = np.array(BG, np.float32)[None, None] + (np.array((92, 104, 140), np.float32) - np.array(BG, np.float32))[None, None] * v[..., None]
        pos = pd.Series(range(len(aid)), index=aid)
        xy = np.zeros((log.n, 2))
        rng = np.random.default_rng(1)
        for i in range(log.n):
            if ids[i] in pos.index:
                x, _, z = axyz[pos[ids[i]]]
                xy[i] = proj(x, z)
            else:                                  # JO / ORN: no soma in the dataset (sensory neurons): schematic clusters above the brain, by side
                sgn = -1.0 if side[i] == "L" else 1.0
                jo = t[i].startswith("JO")
                xy[i] = (MARGIN + (x1 - (x0 + x1) / 2) * self.s + sgn * (0.12 if jo else 0.27) * LW + rng.normal(0, 8), BRAIN_OY - (92 if jo else 48) + rng.normal(0, 8))
        self.xy = xy
        col = np.tile(np.array(VIOLET, np.float32), (log.n, 1))
        hum = np.char.startswith(t.astype("U"), "JO")
        smell = (np.arange(log.n) >= 656) | np.char.startswith(t.astype("U"), "ORN")
        for m, c in ((np.isin(t, ["LC4", "LPLC2", "DNp01", "TTMn"]), RED), (smell, GREEN), (hum, GREEN), (np.isin(t, ["LC10a", "DNp09"]), WHITE)):
            col[m] = c
        self.col = col
        self.rad = np.where(np.isin(t, ["DNp01", "TTMn", "DNp09", "DNa01", "DNa02"]), 4, 2)
        self.groups = dict(loom=np.isin(t, ["LC4", "LPLC2"]), gf=t == "DNp01", jo=hum, home=t == "LC10a", dna=np.isin(t, ["DNa01", "DNa02"]))
        self.static = sil.astype(np.float32)
        self.lab = self._labels()
        self.ring_gf = []

    def centre(self, g):
        return self.xy[self.groups[g]].mean(0)

    def _labels(self):
        """5 labels (looming, Giant Fiber, home, hum / smell, steering) in the margins; leaders chosen among slot assignments so that no leader crosses another leader or any label text."""
        img = Image.new("RGBA", (LW, PH), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        half = lambda g, right: self.xy[self.groups[g] & ((self.xy[:, 0] >= LW / 2) == right)].mean(0)
        f = font(18)
        spec = {"looming": ("looming", half("loom", True), RED), "gf": ("Giant Fiber", self.centre("gf"), RED), "home": ("home", half("home", True), WHITE),
                "hum": ("hum / smell", half("jo", False), GREEN), "dna": ("steering", half("dna", False), VIOLET)}
        yb = BRAIN_OY + (47000.0 - self.z0) * self.s + 30      # side slots: the free margins beside the nerve cord, just below the brain proper (z < 47k)
        right_slots = [(LW - 10, yb + 38 * j, "R") for j in range(3)]
        left_slots = [(10, yb + 38 * j, "L") for j in range(2)]
        top_slot = (10, 16, "L")
        rect = lambda name, sl: (sl[0] - dr.textlength(name, font=f) if sl[2] == "R" else sl[0], sl[1], sl[0] if sl[2] == "R" else sl[0] + dr.textlength(name, font=f), sl[1] + 24)
        anchor = lambda name, sl: ((rect(name, sl)[0] - 6, sl[1] + 12) if sl[2] == "R" else (rect(name, sl)[2] + 6, sl[1] + 12))
        best = None
        for pr in permutations(right_slots, 3):
            for pl in permutations(left_slots, 1):
                assign = {"looming": pr[0], "gf": pr[1], "home": pr[2], "dna": pl[0], "hum": top_slot}
                segs = {k: (anchor(spec[k][0], assign[k]), tuple(spec[k][1])) for k in assign}
                rects = {k: rect(spec[k][0], assign[k]) for k in assign}
                bad = sum(seg_cross(*segs[a], *segs[b]) for a in assign for b in assign if a < b)
                bad += sum(seg_hits_rect(*segs[a], rects[b]) for a in assign for b in assign if a != b)
                length = sum(np.hypot(segs[k][1][0] - segs[k][0][0], segs[k][1][1] - segs[k][0][1]) for k in assign)
                if best is None or (bad, length) < best[0]:
                    best = ((bad, length), assign, segs)
        self.label_bad = best[0][0]
        _, assign, segs = best
        for k, (name, tgt, c) in spec.items():
            sl = assign[k]
            r = rect(name, sl)
            a, b = segs[k]
            dr.line([a, b], fill=tuple(int(v * 0.75) for v in c) + (255,), width=1)
            dr.ellipse([b[0] - 4, b[1] - 4, b[0] + 4, b[1] + 4], outline=c + (255,), width=2)
            dr.text((r[0], r[1]), name, font=f, fill=c + (255,), stroke_width=2, stroke_fill=BG + (255,))
        return np.asarray(img).astype(np.float32)

    def draw(self, k):
        lg = self.log
        b = 0.22 + 0.78 * np.clip(lg.hs[k] / 3.0, 0, 1) ** 0.6
        layer = np.zeros((PH, LW, 3), np.float32)
        for i in np.argsort(b):
            cv2.circle(layer, (int(self.xy[i, 0]), int(self.xy[i, 1])), int(self.rad[i] + (b[i] >= 0.5)), tuple(float(v) * b[i] for v in self.col[i]), -1, cv2.LINE_AA)
        out = self.static[:PH] + layer + cv2.GaussianBlur(layer, (0, 0), 6) * 1.8                 # glow: additive + soft halo
        if k in lg.fire_set:
            self.ring_gf.append(k)
        gx, gy = (int(v) for v in self.centre("gf"))
        if lg.gf[k] >= 0.25 or lg.df.a[k]:                                                        # a steady pulsing ring while it fires
            cv2.circle(out, (gx, gy), int(24 + 6 * np.sin(k * 0.55)), RED, 3, cv2.LINE_AA)
        for k0 in self.ring_gf[-3:]:                                                              # a big expanding ring at the moment it fires
            age = k - k0
            if 0 <= age < 36:
                cv2.circle(out, (gx, gy), int(20 + age * 2.4), tuple(float(v) * (1 - age / 36) for v in RED), 5, cv2.LINE_AA)
        st = lg.dna_steer
        if k > 0 and st[k] < -0.01 <= st[k - 1]:
            self.ring_dna = getattr(self, "ring_dna", []) + [k]
        dx, dy = (int(v) for v in self.centre("dna"))
        for k0 in getattr(self, "ring_dna", [])[-3:]:
            age = k - k0
            if 0 <= age < 24:
                cv2.circle(out, (dx, dy), int(12 + age * 1.6), tuple(float(v) * (1 - age / 24) for v in VIOLET), 3, cv2.LINE_AA)
        al = self.lab[..., 3:4] / 255.0
        out = out * (1 - al) + self.lab[..., :3] * al
        out = np.clip(out, 0, 255).astype(np.uint8)
        fl = [k - k0 for k0 in self.ring_gf if 0 <= k - k0 < 40]
        if fl:                                                                                    # "JUMP" flash above the Giant Fiber
            a = 1 - min(fl) / 40
            pil = Image.fromarray(out)
            ImageDraw.Draw(pil).text((gx, gy - 76), "JUMP", font=font(40), fill=tuple(int(BG[j] + (RED[j] - BG[j]) * a) for j in range(3)), anchor="mm", stroke_width=3, stroke_fill=BG)
            out = np.asarray(pil)
        return out


# ------------------------------------------------------------------------------------------------ game panel
def parse_box(s):
    if not isinstance(s, str) or not s:
        return None
    return tuple(int(v) for v in s.split())


def game_panel(frame, log, k):
    """NES x4 = 1024 x 960 with only the overlay: red loom boxes (pit base thin), green hum line, green smell box."""
    img = cv2.resize(np.ascontiguousarray(frame), None, fx=4, fy=4, interpolation=cv2.INTER_NEAREST).copy()
    r = log.df.iloc[k]
    sl = float(log.sl_pre[k])
    sx = lambda wx: int(round((wx - sl) * 4))
    sy = lambda ty: int(round((ty + 32) * 4))
    box = parse_box(r.box_x_top_w_h)
    if box and r.threat != "none":
        bx, top, bw, bh = box
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 4, cv2.LINE_AA)
    base = parse_box(r.pit_base_x_top_w_h)
    if base:
        bx, top, bw, bh = base
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 1, cv2.LINE_AA)
    if r.hum_level > 0 and not pd.isna(r.hum_block_x):
        bx, bottom = r.hum_block_x, r.hum_bottom
        cv2.line(img, (sx(bx), sy(bottom) + 7), (sx(bx + 16), sy(bottom) + 7), GREEN, 6, cv2.LINE_AA)
    if not pd.isna(r.smell_x):
        bx, top = r.smell_x, r.smell_top
        cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + 16), sy(top + 16)), GREEN, 4, cv2.LINE_AA)
    return img


# ------------------------------------------------------------------------------------------------ data panel (352 x 960): drive icons, JUMP meter, TURN meter, keys, x and score
class DataPanel:
    TT_MAX = 0.30                                  # the JUMP bar is full at TTMn 0.30
    ST_MAX = 0.06                                  # the TURN bar is full at |steer| 0.06

    def __init__(self, log):
        self.log = log
        kn = log.kn
        self.press = kn.TTMN_THRESH
        self.thr = kn.STEER_THRESH

    def draw(self, k):
        lg = self.log
        d = lg.df.iloc[k]
        img = Image.new("RGB", (RW, PH), BG)
        dr = ImageDraw.Draw(img)
        PX = 40                                                    # inner left edge: the first 40 px are the home-marker gutter
        tg = lg.toggles
        # 1. the four drive icons (lit when on)
        for j, (kind, key) in enumerate((("looming", "looming_enemy"), ("home", "home"), ("hum", "hum"), ("smell", "smell"))):
            cx = PX + 38 + j * 76
            icon(dr, cx, 52, 56, kind, bool(tg[key]))
            nm = {"looming": "loom", "home": "home", "hum": "hum", "smell": "smell"}[kind]
            dr.text((cx, 104), nm, font=font(22), fill=TXT if tg[key] else (90, 94, 104), anchor="mm")
        # 2. JUMP meter: TTMn fills toward its threshold line; flashes when A is pressed
        y0, y1, bx0, bx1 = 190, 520, PX + 6, PX + 96
        pressed = bool(d.a)
        dr.text((PX, 138), "JUMP", font=font(34), fill=RED if pressed else (150, 60, 60))
        dr.rectangle([bx0, y0, bx1, y1], fill=(70, 20, 22) if pressed else (16, 18, 24), outline=RED if pressed else (80, 40, 44), width=3)
        fill = min(max(d.ttmn / self.TT_MAX, 0), 1) * (y1 - y0)
        if fill > 3:
            dr.rectangle([bx0 + 3, y1 - fill, bx1 - 3, y1 - 2], fill=RED if pressed else (200, 64, 64))
        ty = y1 - self.press / self.TT_MAX * (y1 - y0)
        dr.line([(bx0 - 12, ty), (bx1 + 12, ty)], fill=(255, 220, 90), width=3)
        dr.text((bx1 + 18, ty), f"press {self.press:.2f}", font=font(22), fill=(255, 220, 90), anchor="lm")
        dr.text((bx1 + 18, y0 + 14), f"TTMn", font=font(22), fill=TXT, anchor="lm")
        dr.text((bx1 + 18, y0 + 44), f"{d.ttmn:.3f}", font=font(30), fill=TXT, anchor="lm")
        if pressed:
            dr.text((bx1 + 18, y1 - 14), "A pressed", font=font(22), fill=RED, anchor="lm")
        # 3. TURN meter: centre = straight, left / right fill = steer, the +-threshold marks
        ty0, ty1, mx0, mx1 = 628, 668, PX, RW - 16
        mid = (mx0 + mx1) / 2
        half = (mx1 - mx0) / 2
        dr.text((PX, 576), "TURN", font=font(34), fill=VIOLET)
        dr.rectangle([mx0, ty0, mx1, ty1], fill=(16, 18, 24), outline=(70, 60, 100), width=3)
        sv = float(np.clip(d.steer, -self.ST_MAX, self.ST_MAX)) / self.ST_MAX * half
        dr.rectangle([min(mid, mid + sv), ty0 + 3, max(mid, mid + sv), ty1 - 3], fill=VIOLET)
        for sgn in (-1, 1):
            xx = mid + sgn * self.thr / self.ST_MAX * half
            dr.line([(xx, ty0 - 8), (xx, ty1 + 8)], fill=(255, 220, 90), width=3)
        dr.line([(mid, ty0 - 4), (mid, ty1 + 4)], fill=(200, 200, 210), width=2)
        dr.text((mx0, ty1 + 26), "← left", font=font(22), fill=TXT, anchor="lm")
        dr.text((mx1, ty1 + 26), "right →", font=font(22), fill=TXT, anchor="rm")
        dr.text((mid, ty1 + 26), f"{d.steer:+.3f}", font=font(22), fill=TXT, anchor="mm")
        # 4. the buttons as lit keys
        for j, (nm, on) in enumerate((("←", bool(d.left)), ("→", bool(d.right)), ("A", bool(d.a)))):
            x = PX + j * 104
            dr.rounded_rectangle([x, 742, x + 92, 822], 12, fill=(238, 238, 244) if on else (24, 27, 36), outline=(120, 126, 142), width=3)
            dr.text((x + 46, 782), nm, font=font(44), fill=(20, 22, 30) if on else (100, 104, 116), anchor="mm")
        # 5. x and score as large numbers
        dr.text((PX, 840), "x", font=font(26), fill=DIM)
        dr.text((RW - 16, 868), f"{int(d.x)}", font=font(56), fill=TXT, anchor="rm")
        dr.text((PX, 900), "score", font=font(26), fill=DIM)
        dr.text((RW - 16, 928), f"{int(d.score)}", font=font(56), fill=TXT, anchor="rm")
        return np.asarray(img)


# ------------------------------------------------------------------------------------------------ the whole frame
class Renderer:
    def __init__(self, log, label=None):
        self.log = log
        self.brain, self.data = BrainPanel(log), DataPanel(log)
        ep = log.meta["episode"]
        self.label = label or f"arm {log.arm} · noop {ep['noop_start']} · σ {ep['sigma']:g}"

    def frame(self, nes_frame, k):
        lg = self.log
        out = np.zeros((H, W, 3), np.uint8)
        out[:] = BG
        out[TOP:TOP + PH, :LW] = self.brain.draw(k)
        out[TOP:TOP + PH, RX0:] = self.data.draw(k)
        out[TOP:TOP + PH, MX0:MX0 + MW] = game_panel(nes_frame, lg, k)
        if lg.toggles["home"]:                  # the home marker: a white dot just outside the game's right edge at his eye height; opacity ~ HOME_R
            eye = lg.feet_pre[k] - (24 if lg.pow_pre[k] >= 1 else 16)
            cy = TOP + int(round((eye + 32) * 4))
            ov = out.copy()
            cv2.circle(ov, (RX0 + 20, cy), 12, WHITE, -1, cv2.LINE_AA)
            a = min(1.0, lg.kn.HOME_R)
            out = cv2.addWeighted(ov, a, out, 1 - a, 0)
        pil = Image.fromarray(out)
        dr = ImageDraw.Draw(pil)
        dr.rectangle([0, 0, W, TOP], fill=(10, 12, 18))
        dr.text((20, TOP // 2), "MaleCNS fruit-fly brain plays Super Mario Bros 1-1", font=font(30), fill=TXT, anchor="lm")
        tg = lg.toggles
        x = W - 20
        for kind, key in reversed((("looming", "looming_enemy"), ("home", "home"), ("hum", "hum"), ("smell", "smell"))):
            icon(dr, x - 20, TOP // 2, 36, kind, bool(tg[key]))
            x -= 56
        dr.text((x - 12, TOP // 2), self.label, font=font(24), fill=(196, 202, 216), anchor="rm")
        dr.rectangle([0, H - BOT, W, H], fill=(10, 12, 18))
        co = lg.callout(k)
        if co:
            text, col, a = co
            dr.text((W // 2, H - BOT // 2), text, font=font(32), fill=tuple(int(10 + (col[j] - 10) * a) for j in range(3)), anchor="mm")
        for xx in (LW, RX0):
            dr.line([(xx, TOP), (xx, H - BOT)], fill=(30, 34, 44), width=1)
        return np.asarray(pil)


def title_card(log, path):
    """One PNG: the knob values with their provenance tags (teal = from the fly, orange = invented) and the colour language."""
    kn = log.kn
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    dr.text((W // 2, 110), "MaleCNS fruit-fly brain plays Super Mario Bros 1-1", font=font(54), fill=TXT, anchor="mm")
    dr.text((W // 2, 180), "a real connectome circuit drives the game; nothing is trained", font=font(30), fill=DIM, anchor="mm")
    dr.text((120, 270), "from the fly", font=font(30), fill=TEAL)
    dr.text((120, 316), f"MaleCNS v1.0 · {log.n} neurons · {int((log.brain.W != 0).sum()):,} synapse pairs", font=font(24), fill=TXT)
    dr.text((120, 350), "cell types · real wiring · real signs", font=font(24), fill=TXT)
    dr.text((120, 430), "invented (set by hand, tagged orange)", font=font(30), fill=ORANGE)
    kv = [("HOME_R", kn.HOME_R), ("G", kn.G), ("ALPHA", kn.ALPHA), ("CLIP", f"{kn.CLIP:g}"), ("SUBSTEPS", kn.SUBSTEPS), ("TTMN_THRESH", kn.TTMN_THRESH), ("DNP09_THRESH", kn.DNP09_THRESH),
          ("STEER_THRESH", kn.STEER_THRESH), ("HUM_GAIN", kn.HUM_GAIN), ("SMELL_GAIN", kn.SMELL_GAIN), ("SENSOR_NOISE", f"{log.meta['episode']['sigma']:g}"), ("MARIO_BOX", "12x16 small · 12x24 big")]
    for j, (a, b) in enumerate(kv):
        cx, cy = 120 + (j % 2) * 520, 486 + (j // 2) * 44
        dr.ellipse([cx, cy + 8, cx + 14, cy + 22], fill=ORANGE)
        dr.text((cx + 28, cy), f"{a}  {b}", font=font(26), fill=TXT)
    dr.text((1240, 270), "colour language", font=font(30), fill=TXT)
    for j, (nm, c, what) in enumerate((("red", RED, "looming: LC4, LPLC2, Giant Fiber, TTMn"), ("green", GREEN, "hum and smell: JO, ORNs, PN, LAL030"), ("white", WHITE, "home: LC10a, DNp09"),
                                       ("violet", VIOLET, "steering: DNa"))):
        y = 326 + j * 52
        dr.rectangle([1240, y + 4, 1270, y + 34], fill=c)
        dr.text((1290, y), f"{nm}  {what}", font=font(26), fill=TXT)
    dr.text((1240, 560), "game: the NES frame; boxes, line and dot are what", font=font(24), fill=DIM)
    dr.text((1240, 596), "the fly's senses read from RAM", font=font(24), fill=DIM)
    dr.text((W // 2, H - 70), f"{log.label if hasattr(log, 'label') else ''}", font=font(24), fill=DIM, anchor="mm")
    img.save(path)
    return path
