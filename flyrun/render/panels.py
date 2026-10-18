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
from . import log as L

W, H, TITLE_H = 1920, 1080, 44
LW, MW, RW = 576, 768, 576
MX0, RX0 = LW, LW + MW
GAME_Y = TITLE_H + (H - TITLE_H - 720) // 2
BG = (14, 16, 22)
GREY = (66, 72, 84)
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
        self.gf = self.h[:, br.masks["DNp01"]].mean(1)
        self.dna_steer = d.steer.to_numpy()
        # "the Giant Fiber fires": DNp01 crosses 0.25 upward, or a grounded A press starts (the jump itself); events within 10 frames of an earlier one are merged
        up = np.flatnonzero((self.gf[1:] >= 0.25) & (self.gf[:-1] < 0.25)) + 1
        on = d.index[(d.a == 1) & (d.a.shift(1, fill_value=0) == 0) & (d.airborne == 0)].to_numpy()
        self.fire = []
        for f in sorted(set(up.tolist()) | set(on.tolist())):
            if not self.fire or f - self.fire[-1] > 10:
                self.fire.append(int(f))
        self.toggles = self.meta["toggles"]
        self.fire_set = set(self.fire)

    def __len__(self):
        return len(self.df)


# ------------------------------------------------------------------------------------------------ brain panel
# View: the brain only, cropped to x 20k..78k, z 8k..48k (voxel units) and scaled to the panel width (~1.75x the uncropped fit); the nerve cord is a small inset that shows TTMn only.
VIEW_X0, VIEW_X1, VIEW_Z0, VIEW_Z1 = 20000.0, 78000.0, 8000.0, 48000.0
VIEW_OY = 214                                  # panel y of VIEW_Z0 (room above for the JO / ORN schematic clusters)
INSET = (14, 700, 254, 1046)                   # x0, y0, x1, y1 of the VNC inset
INSET_X0, INSET_Z0, INSET_Z1 = 49000.0 - 26000.0, 58000.0, 136000.0


class BrainPanel:
    def __init__(self, log):
        self.log = log
        br = log.brain
        t = br.bodies.type.astype(str).to_numpy()
        side = br.bodies.somaSide.astype(str).to_numpy()
        ids = br.bodies.bodyId.to_numpy()
        aid, axyz = L.soma_all()
        axyz = axyz.astype(np.float64)
        self.s = (LW - 12) / (VIEW_X1 - VIEW_X0)
        self.si = (INSET[3] - INSET[1]) / (INSET_Z1 - INSET_Z0)
        proj = lambda x, z: (6 + (VIEW_X1 - x) * self.s, VIEW_OY + (z - VIEW_Z0) * self.s)    # flipped x: the fly's LEFT is on the viewer's left, like the game's right
        proji = lambda x, z: (INSET[0] + (INSET_X0 + (INSET[2] - INSET[0]) / self.si - x) * self.si, INSET[1] + (z - INSET_Z0) * self.si)
        # grey silhouette: density of all 141,781 somata, brain view and the VNC inset
        hist = np.zeros((H, LW), np.float32)
        px, py = proj(axyz[:, 0], axyz[:, 2])
        ok = (px >= 0) & (px < LW) & (py >= 0) & (py < H) & (axyz[:, 2] < VIEW_Z1 + 4000)
        np.add.at(hist, (py[ok].astype(int), px[ok].astype(int)), 1.0)
        px, py = proji(axyz[:, 0], axyz[:, 2])
        ok = (px >= INSET[0]) & (px < INSET[2]) & (py >= INSET[1]) & (py < INSET[3]) & (axyz[:, 2] >= INSET_Z0)
        np.add.at(hist, (py[ok].astype(int), px[ok].astype(int)), 1.0)
        hist = cv2.GaussianBlur(hist, (0, 0), 1.4)
        v = np.clip(np.log1p(hist * 6) / np.log1p(hist.max() * 6 * 0.5), 0, 1)
        bg = np.array(BG, np.float32)
        sil = bg[None, None] + (np.array(GREY, np.float32) - bg)[None, None] * v[..., None]
        # positions of the 881
        pos = pd.Series(range(len(aid)), index=aid)
        xy = np.zeros((self.log.n, 2))
        rng = np.random.default_rng(1)
        for i in range(self.log.n):
            if ids[i] in pos.index:
                x, _, z = axyz[pos[ids[i]]]
                xy[i] = proji(x, z) if t[i] == "TTMn" else proj(x, z)
            else:                                  # JO / ORN: no soma in the dataset (sensory neurons); schematic cluster above the brain, by side
                sgn = -1.0 if side[i] == "L" else 1.0
                jo = t[i].startswith("JO")
                cx = 6 + (VIEW_X1 - 49000.0) * self.s + sgn * (0.12 if jo else 0.27) * LW
                xy[i] = (cx + rng.normal(0, 8), VIEW_OY - (96 if jo else 52) + rng.normal(0, 8))
        self.xy = xy
        # drive colours
        col = np.tile(np.array(NEUTRAL, np.float32), (self.log.n, 1))
        hum = np.char.startswith(t.astype("U"), "JO")
        smell = (np.arange(self.log.n) >= 656) | np.char.startswith(t.astype("U"), "ORN")
        loom = np.isin(t, ["LC4", "LPLC2", "DNp01", "TTMn"])
        home = np.isin(t, ["LC10a", "DNp09"])
        for m, c in ((loom, RED), (smell, GREEN), (hum, GREEN), (home, WHITE)):
            col[m] = c
        self.col = col
        self.rad = np.where(np.isin(t, ["DNp01", "TTMn", "DNp09", "DNa01", "DNa02"]), 4, 2)
        self.groups = dict(loom=np.isin(t, ["LC4", "LPLC2"]), gf=t == "DNp01", ttmn=t == "TTMn", jo=hum, orn=np.char.startswith(t.astype("U"), "ORN"), smell=smell & ~hum, home=t == "LC10a", dnp09=t == "DNp09", dna=np.isin(t, ["DNa01", "DNa02"]))
        # static layer: silhouette, labels at the panel edges with short leaders (sorted by height per side, so they cannot cross), inset frame
        img = Image.fromarray(np.clip(sil, 0, 255).astype(np.uint8))
        dr = ImageDraw.Draw(img)
        dr.text((10, 52), "BRAIN  881 real neurons (MaleCNS v1.0)", font=font(15), fill=TXT)
        dr.text((10, 74), "grey: all 141,781 somata    bright: the 881, by rate", font=font(11), fill=DIM)
        # labels live in their own layer drawn ON TOP of the bright neurons; each points at the cluster of its drive that is active (right side for looming / home)
        lab = Image.new("RGBA", (LW, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lab)
        half = lambda g, right: self.xy[self.groups[g] & ((self.xy[:, 0] >= LW / 2) == right)].mean(0)
        labels = [("looming  LC4 / LPLC2", half("loom", True), RED), ("Giant Fiber", self.centre("gf"), RED), ("hum  JO", half("jo", False), GREEN), ("smell  ORN > PN > LAL030", half("orn", True), GREEN),
                  ("home  LC10a", half("home", True), WHITE), ("DNp09  walk", self.centre("dnp09"), WHITE), ("DNa  steer", half("dna", False), NEUTRAL)]
        for side_name, items in (("L", [a_ for a_ in labels if a_[1][0] < LW / 2]), ("R", [a_ for a_ in labels if a_[1][0] >= LW / 2])):
            items = sorted(items, key=lambda a_: a_[1][1])
            ys = []
            for name, (cx, cy), c in items:
                ty = cy - 8
                if ys and ty < ys[-1] + 26:
                    ty = ys[-1] + 26
                ys.append(ty)
            for (name, (cx, cy), c), ty in zip(items, ys):
                tw = dl.textlength(name, font=font(14))
                tx = 6 if side_name == "L" else LW - 6 - tw
                ex = tx + tw + 5 if side_name == "L" else tx - 5
                if (side_name == "R" and cx > ex) or (side_name == "L" and cx < ex):          # the cluster lies beside / above the text: leave from its top or bottom edge, never through it
                    sx0, sy0 = min(max(cx, tx), tx + tw), (ty if cy < ty else ty + 18)
                else:
                    sx0, sy0 = ex, ty + 9
                dl.line([(sx0, sy0), (cx, cy)], fill=tuple(int(v * 0.7) for v in c) + (255,), width=1)
                dl.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=c + (255,))
                dl.text((tx, ty), name, font=font(14), fill=c + (255,), stroke_width=2, stroke_fill=BG + (255,))
        tx, ty = self.xy[self.groups["ttmn"]].mean(0)
        dl.text((INSET[2] - 6, INSET[1] + 24), "TTMn", font=font(14), fill=RED + (255,), stroke_width=2, stroke_fill=BG + (255,), anchor="ra")
        dl.line([(INSET[2] - 56, INSET[1] + 33), (tx + 4, ty)], fill=tuple(int(v * 0.7) for v in RED) + (255,), width=1)
        self.lab = np.asarray(lab).astype(np.float32)
        dr.rectangle(INSET, outline=(52, 56, 68))
        dr.text((INSET[0] + 6, INSET[1] + 4), "nerve cord (VNC)", font=font(12), fill=DIM)
        ky = INSET[1] + 6
        for name, c in (("looming", RED), ("hum / smell", GREEN), ("home", WHITE), ("steering, relays", NEUTRAL)):
            dr.ellipse([290, ky + 4, 300, ky + 14], fill=c)
            dr.text((308, ky), name, font=font(13), fill=TXT)
            ky += 22
        dr.text((290, ky + 10), "brightness = rate", font=font(12), fill=DIM)
        dr.text((290, ky + 28), "JO / ORN have no soma in the", font=font(11), fill=DIM)
        dr.text((290, ky + 43), "data: drawn as schematic", font=font(11), fill=DIM)
        dr.text((290, ky + 58), "clusters above the head", font=font(11), fill=DIM)
        self.static = np.asarray(img).astype(np.float32)
        self.ring_gf, self.ring_dna = [], []

    def centre(self, g):
        return self.xy[self.groups[g]].mean(0)

    def draw(self, k):
        lg = self.log
        b = 0.20 + 0.80 * np.clip(lg.hs[k] / 3.0, 0, 1) ** 0.6
        layer = np.zeros((H, LW, 3), np.float32)
        for i in np.argsort(b):
            cv2.circle(layer, (int(self.xy[i, 0]), int(self.xy[i, 1])), int(self.rad[i] + (b[i] >= 0.5)), tuple(float(v) * b[i] for v in self.col[i]), -1, cv2.LINE_AA)
        out = self.static + layer + cv2.GaussianBlur(layer, (0, 0), 5) * 1.6
        al = self.lab[..., 3:4] / 255.0
        out = out * (1 - al) + self.lab[..., :3] * al
        gf, st = lg.gf, lg.dna_steer
        if k in lg.fire_set:
            self.ring_gf.append(k)
        if k > 0 and st[k] < -0.01 <= st[k - 1]:
            self.ring_dna.append(k)
        gx, gy = (int(v) for v in self.centre("gf"))
        if gf[k] >= 0.25 or lg.df.a[k]:                                    # a steady pulsing ring while it is firing
            cv2.circle(out, (gx, gy), int(24 + 6 * np.sin(k * 0.55)), RED, 3, cv2.LINE_AA)
        for k0 in self.ring_gf[-3:]:                                       # a big expanding ring at the moment it fires
            age = k - k0
            if 0 <= age < 36:
                a = 1 - age / 36
                cv2.circle(out, (gx, gy), int(20 + age * 2.4), tuple(float(v) * a for v in RED), 5, cv2.LINE_AA)
        dx, dy = (int(v) for v in self.centre("dna"))
        for k0 in self.ring_dna[-3:]:
            age = k - k0
            if 0 <= age < 24:
                cv2.circle(out, (dx, dy), int(12 + age * 1.6), tuple(float(v) * (1 - age / 24) for v in NEUTRAL), 3, cv2.LINE_AA)
        out = np.clip(out, 0, 255).astype(np.uint8)
        fl = [k - k0 for k0 in self.ring_gf if 0 <= k - k0 < 40]
        if fl:                                                             # "JUMP" flash above the Giant Fiber
            a = 1 - min(fl) / 40
            pil = Image.fromarray(out)
            ImageDraw.Draw(pil).text((gx, gy - 74), "JUMP", font=font(34), fill=tuple(int(BG[j] + (RED[j] - BG[j]) * a) for j in range(3)), anchor="mm", stroke_width=3, stroke_fill=BG)
            out = np.asarray(pil)
        return out


# ------------------------------------------------------------------------------------------------ game panel
def parse_box(s):
    if not isinstance(s, str) or not s:
        return None
    return tuple(int(v) for v in s.split())


def game_panel(frame, log, k):
    """The NES frame x3 with the red / green overlay (the home circle is drawn outside the game frame, in Renderer)."""
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
    return img


# ------------------------------------------------------------------------------------------------ data panel
SPAN = 180
PAD_L, GUT_R = 44, 84                 # left gutter (the home circle sits in the first 44 px, just right of the game), right gutter for the threshold labels
BOX_X0, BOX_X1 = PAD_L + 10, RW - GUT_R
TOP, TRACE_H = 134, 700               # the traces share this much height; the buttons and knobs sit below
TRACES = [("looming", "theta of the chosen threat (deg)", 0, 90, RED), ("hum", "hum level (JO input)", 0, 10, GREEN), ("smell", "smell L / R (ORN input)", 0, 80, GREEN),
          ("ttmn", "TTMn (jump motor neuron)", 0, 0.6, RED), ("steer", "steer = DNa R - L", -0.06, 0.06, NEUTRAL)]


def visible_traces(tg):
    """Traces of drives that are OFF are hidden (their space goes to the rest): theta needs looming; hum needs hum; smell needs smell; TTMn needs looming or hum; steer needs home or smell."""
    loom = tg["looming_enemy"] or tg["looming_pipe"] or tg["looming_pit"]
    on = dict(looming=loom, hum=tg["hum"], smell=tg["smell"], ttmn=loom or tg["hum"], steer=tg["home"] or tg["smell"])
    return [i for i, t in enumerate(TRACES) if on[t[0]]]


class DataPanel:
    def __init__(self, log):
        self.log = log
        d = log.df
        self.series = [np.degrees(d.theta.to_numpy()), d.hum_level.fillna(0).to_numpy(), (d.smell_L.fillna(0).to_numpy(), d.smell_R.fillna(0).to_numpy()), d.ttmn.to_numpy(), d.steer.to_numpy()]
        kn = log.kn
        self.press, self.release = kn.TTMN_THRESH, (kn.RELEASE_THRESH if kn.RELEASE_THRESH is not None else kn.TTMN_THRESH)
        self.vis = visible_traces(log.toggles)
        slot = TRACE_H / len(self.vis)
        self.th = int(min(slot - 44, 190))
        self.pos = {i: TOP + int(j * slot) + 30 for j, i in enumerate(self.vis)}          # y of each trace box's top
        self.knob_y = 856
        img = Image.new("RGB", (RW, H), BG)
        dr = ImageDraw.Draw(img)
        dr.text((10, 52), "DATA  (last 3 s)", font=font(15), fill=TXT)
        x = 10
        tg = log.toggles
        for nm, key in (("looming", "looming_enemy"), ("home", "home"), ("hum", "hum"), ("smell", "smell")):
            on = bool(tg[key])
            c = {"looming": RED, "home": WHITE, "hum": GREEN, "smell": GREEN}[nm]
            lab = nm + (" ON" if on else "")
            w = int(dr.textlength(lab, font=font(16))) + 26
            dr.rounded_rectangle([x, 74, x + w, 100], 13, outline=c if on else (60, 64, 74), fill=tuple(int(v * 0.30) for v in c) if on else None, width=2)
            dr.text((x + 13, 77), lab, font=font(16), fill=c if on else (90, 94, 104))
            x += w + 10
        for i in self.vis:
            _, title, lo, hi, c = TRACES[i]
            y = self.pos[i]
            dr.text((PAD_L + 10, y - 27), title, font=font(18), fill=c)
            dr.rectangle([BOX_X0, y, BOX_X1, y + self.th], outline=(46, 50, 60))
            yv = lambda v: y + self.th - (v - lo) / (hi - lo) * self.th
            if i == 3:                                                  # thresholds: lines inside the trace, labels OUTSIDE (right gutter)
                dr.line([(BOX_X0, yv(self.press)), (BOX_X1, yv(self.press))], fill=(150, 150, 70), width=1)
                if self.press == self.release:
                    dr.text((BOX_X1 + 5, yv(self.press) - 17), "press =", font=font(11), fill=(170, 170, 90))
                    dr.text((BOX_X1 + 5, yv(self.press) - 4), f"release {self.press:.2f}", font=font(11), fill=(170, 170, 90))
                else:
                    for nm, v in (("press", self.press), ("release", self.release)):
                        dr.text((BOX_X1 + 6, yv(v) - 8), f"{nm} {v:.2f}", font=font(12), fill=(170, 170, 90))
            if i == 4:
                for v, nm in ((0.01, "+0.01  R"), (-0.01, "-0.01  L")):
                    dr.line([(BOX_X0, yv(v)), (BOX_X1, yv(v))], fill=(150, 110, 70), width=1)
                    dr.text((BOX_X1 + 6, yv(v) - 8), nm, font=font(12), fill=(190, 140, 90))
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
        self.static = np.asarray(img)

    def draw(self, k):
        lg = self.log
        img = self.static.copy()
        lo_k = max(0, k - SPAN + 1)
        xs = np.arange(lo_k, k + 1)
        for i in self.vis:
            _, title, lo, hi, c = TRACES[i]
            y = self.pos[i]
            ser = self.series[i]
            lines = [(ser, c)] if i != 2 else [(ser[0], (120, 255, 150)), (ser[1], (30, 160, 70))]
            for s, col in lines:
                v = np.clip(s[lo_k:k + 1], lo, hi)
                px = BOX_X0 + (xs - (k - SPAN + 1)) / (SPAN - 1) * (BOX_X1 - BOX_X0)
                py = y + self.th - (v - lo) / (hi - lo) * self.th
                pts = np.stack([px, py], 1).astype(np.int32).reshape(-1, 1, 2)
                if len(pts) > 1:
                    cv2.polylines(img, [pts], False, col, 2, cv2.LINE_AA)
        pil = Image.fromarray(img)
        dr = ImageDraw.Draw(pil)
        d = lg.df.iloc[k]
        vals = [f"{np.degrees(d.theta):.0f}°", f"{0 if pd.isna(d.hum_level) else d.hum_level:.1f}", f"L {d.smell_L:.0f}  R {d.smell_R:.0f}", f"{d.ttmn:.3f}", f"{d.steer:+.3f}"]
        for i in self.vis:
            dr.text((BOX_X1, self.pos[i] - 27), vals[i], font=font(18), fill=TXT, anchor="ra")
        by = self.knob_y
        for j, (nm, on) in enumerate([("←", bool(d.left)), ("→", bool(d.right)), ("A", bool(d.a))]):
            x = 10 + j * 56
            dr.rounded_rectangle([x, by, x + 48, by + 44], 8, fill=(236, 236, 240) if on else (30, 34, 44), outline=(110, 116, 130), width=2)
            dr.text((x + 24, by + 22), nm, font=font(22), fill=(20, 22, 30) if on else (96, 100, 112), anchor="mm")
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

    def frame(self, nes_frame, k):
        lg = self.log
        out = np.zeros((H, W, 3), np.uint8)
        out[:] = BG
        out[:, :LW] = self.brain.draw(k)[:H]
        out[:, RX0:] = self.data.draw(k)[:H]
        out[GAME_Y:GAME_Y + 720, MX0:MX0 + MW] = game_panel(nes_frame, lg, k)
        if lg.toggles["home"]:                  # the home marker: OUTSIDE the game frame, just right of it, at his eye height; size / opacity ~ HOME_R
            eye = lg.feet_pre[k] - (24 if lg.pow_pre[k] >= 1 else 16)
            cy = GAME_Y + int(round((eye + 32) * 3))
            a = min(1.0, lg.kn.HOME_R)
            ov = out.copy()
            cv2.circle(ov, (RX0 + 22, cy), int(5 + 16 * lg.kn.HOME_R), WHITE, -1, cv2.LINE_AA)
            out = cv2.addWeighted(ov, a, out, 1 - a, 0)
        pil = Image.fromarray(out)
        dr = ImageDraw.Draw(pil)
        dr.rectangle([0, 0, W, TITLE_H], fill=(22, 25, 34))
        dr.text((16, 10), "MaleCNS fruit-fly brain plays Super Mario Bros 1-1", font=font(20), fill=TXT)
        right = f"{self.label}     frame {k}"
        dr.text((W - 16 - dr.textlength(right, font=font(18)), 12), right, font=font(18), fill=(190, 196, 210))
        ly = TITLE_H + 56                       # the colour key lives in the black band above the game
        x = MX0 + 24
        for nm, c in (("looming", RED), ("hum / smell", GREEN), ("home", WHITE)):
            dr.rectangle([x, ly + 4, x + 20, ly + 24], fill=c)
            dr.text((x + 30, ly), nm, font=font(18), fill=TXT)
            x += 40 + int(dr.textlength(nm, font=font(18))) + 44
        dr.text((MX0 + 24, ly + 40), "the game as the fly's senses read it from RAM", font=font(13), fill=DIM)
        for xx in (LW, RX0):
            dr.line([(xx, TITLE_H), (xx, H)], fill=(40, 44, 54), width=1)
        return np.asarray(pil)
