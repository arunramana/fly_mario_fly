"""R3: the OLD two-panel layout (1920 x 1080, black): LEFT = the live brain panel (896 px; a 640 px content column centred: the brain, the nerve cord, a text block, the INDEX), RIGHT = the game, NES x4 =
1024 x 960 right-aligned and vertically centred. Everything is drawn from the logs (a Log object); the emulator only supplies the NES frames. No arrows, no leader lines, no meters.
Copied from the old tool's render/brain_panel.py (read-only reference, nothing imported from it) and adapted: the soma-cloud construction (`_build`: project every somaLocation with x against z, log-density grey
background), the COL / LABEL tables (colours and names of the populations), the legend row style (dot, label, 100 px bar, value) and the 'LIVE BRAIN' text-strip wording. New here: per-neuron glow (additive + halo),
per-group colours for the 881, the JO / ORN positions (sensory.py), the nerve cord at its own scale, the index with dimmed rows for drives that are off."""
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .. import c1_run as C
from . import log as L
from . import sensory

W, H = 1920, 1080
LEFT_W, COL_W, COL_X = 896, 640, 128                # the left panel and its content column
GAME_X, GAME_Y, GAME_W, GAME_H = 896, 60, 1024, 960
BG = (6, 6, 8)
TEAL, ORANGE, DIM, TXT = (40, 200, 190), (255, 150, 40), (130, 130, 124), (205, 204, 196)
YELLOW = (250, 215, 60)                                  # sour
WHITE, RED, GREEN = (240, 240, 240), (255, 72, 72), (64, 224, 96)     # the game overlay colours (loom boxes, hum line / smell box)
FONT, FONT_B = "C:/Windows/Fonts/DejaVuSans.ttf", "C:/Windows/Fonts/DejaVuSans-Bold.ttf"
_F = {}


def font(sz, bold=False):
    if (sz, bold) not in _F:
        _F[(sz, bold)] = ImageFont.truetype(FONT_B if bold else FONT, sz)
    return _F[(sz, bold)]


# Group colours (the old tool's COL where it had one), identical in the brain and in the index dot. (name, role, colour, drives that light the row)
GROUPS = [("LC4", "looming", (57, 135, 229), ("looming",)), ("LPLC2", "looming", (25, 158, 112), ("looming",)), ("DNp01", "Giant Fiber", (217, 89, 38), ("looming", "hum")),
          ("TTMn", "jump muscle", (230, 103, 103), ("looming", "hum")), ("DNa L", "steering", (168, 121, 224), ("home", "smell")), ("DNa R", "steering", (222, 178, 60), ("home", "smell")),
          ("DNp09", "forward walking", (99, 200, 226), ("home",)), ("LC10a", "home", (235, 235, 235), ("home",)), ("JO", "hum (hearing)", (240, 140, 200), ("hum",)), ("ORN", "smell", (200, 200, 90), ("smell",))]
AV1_GROUPS = [("DC4 sour", "acid smell", (250, 215, 60), ("sour",)), ("MDN back up", "moonwalker", (255, 128, 64), ("sour",))]      # AV1: only in the sour brain (the 907-neuron one)
OTHER = (110, 118, 130)                               # the other relays of the 636-neuron steering / looming circuit: neutral, glowing with their own rate, no index row


# ------------------------------------------------------------------------------------------------ the run's log
class Log:
    def __init__(self, base, knobs=None, brain=None):
        base = str(base)
        self.df = pd.read_csv(base + ".csv")
        self.h = np.load(base + ".npz")["h"].astype(np.float32)
        import json
        self.meta = json.load(open(base + ".json"))
        self.arm = self.meta["arm"]
        self.kn = knobs or replace(C.KN, **C.ARMS[self.arm], **self.meta.get("knob_overrides", {}))
        br = brain or C._brain()
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
        up = np.flatnonzero((self.gf[1:] >= 0.25) & (self.gf[:-1] < 0.25)) + 1          # "the Giant Fiber fires" (used to pick stills)
        on = d.index[(d.a == 1) & (d.a.shift(1, fill_value=0) == 0) & (d.airborne == 0)].to_numpy()
        self.fire = []
        for f in sorted(set(up.tolist()) | set(on.tolist())):
            if not self.fire or f - self.fire[-1] > 10:
                self.fire.append(int(f))
        self.fire_set = set(self.fire)
        self.toggles = self.meta["toggles"]

    def drive_on(self, name):
        tg = self.toggles
        return {"looming": tg["looming_enemy"] or tg["looming_pipe"] or tg["looming_pit"], "home": tg["home"], "hum": tg["hum"], "smell": tg["smell"], "sour": tg.get("sour", False)}[name]

    def __len__(self):
        return len(self.df)


# ------------------------------------------------------------------------------------------------ the brain panel (896 x 1080)
BRAIN_Y0 = 22                                        # top of the brain
VNC_Y0, VNC_H = 300, 262                             # the nerve cord, drawn at its own (smaller) scale so everything fits above the text block
Z_SPLIT = 52000.0                                    # somata with z below this are brain, above are nerve cord (the data has a gap there)


def _smooth_grey(dens):
    """The old `_build` tone: log density -> grey (70, 78, 74) clipped, on the black surface."""
    """R3b: every soma is a 1-px point at low alpha (additive, no blur): one soma = 15 grey levels, capped where they pile up, so the cloud reads as fine points, not blobs."""
    v = np.clip(dens * 15.0, 0, 70)
    out = np.zeros(dens.shape + (3,), np.float32)
    for c, base in enumerate((70, 78, 74)):
        out[..., c] = np.maximum(v * base / 70.0, BG[c])
    return out


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
        self.s = (COL_W - 12) / (x1 - x0)
        vn = axyz[:, 2] >= Z_SPLIT
        vx0, vx1, vz0, vz1 = axyz[vn, 0].min(), axyz[vn, 0].max(), axyz[vn, 2].min(), axyz[vn, 2].max()
        self.sv = VNC_H / (vz1 - vz0)
        # flipped x: the fly's LEFT is on the viewer's left, like the game's right
        proj = lambda x, z: (COL_X + 6 + (x1 - x) * self.s, BRAIN_Y0 + (z - z0) * self.s)
        projv = lambda x, z: (COL_X + COL_W / 2 + ((vx0 + vx1) / 2 - x) * self.sv, VNC_Y0 + (z - vz0) * self.sv)
        dens_b, dens_v = np.zeros((H, LEFT_W), np.float32), np.zeros((H, LEFT_W), np.float32)
        px, py = proj(axyz[~vn, 0], axyz[~vn, 2])
        np.add.at(dens_b, (py.astype(int), px.astype(int)), 1.0)
        px, py = projv(axyz[vn, 0], axyz[vn, 2])
        np.add.at(dens_v, (py.astype(int), px.astype(int)), 1.0)
        self.bg = np.maximum(_smooth_grey(dens_b), _smooth_grey(dens_v))
        pos = pd.Series(range(len(aid)), index=aid)
        xy = np.zeros((log.n, 2))
        jo_orn = ~np.isin(ids, aid)                            # no soma in MaleCNS: the 20 JO, the 163 ORNs and one relay
        sp = sensory.positions(ids[jo_orn])                    # drawn at the mean soma position of their output partners, inside the brain
        spi = iter(sp)
        for i in range(log.n):
            if jo_orn[i]:
                x, _, z = next(spi)
                xy[i] = proj(x, z)
            else:
                x, _, z = axyz[pos[ids[i]]]
                xy[i] = projv(x, z) if z >= Z_SPLIT else proj(x, z)
        self.xy = xy
        # group membership (index rows) and colours; the smell-path intermediates take the ORN colour, the rest of the circuit is neutral
        idx = np.arange(log.n)
        self.members = {
            "LC4": t == "LC4", "LPLC2": t == "LPLC2", "DNp01": t == "DNp01", "TTMn": t == "TTMn",
            "DNa L": np.isin(t, ["DNa01", "DNa02"]) & (side == "L"), "DNa R": np.isin(t, ["DNa01", "DNa02"]) & (side == "R"),
            "DNp09": t == "DNp09", "LC10a": t == "LC10a", "JO": np.char.startswith(t.astype("U"), "JO"),
            "ORN": (np.char.startswith(t.astype("U"), "ORN") & (t != "ORN_DC4")) | ((idx >= 656) & ~((idx >= 881) & (log.n > 881)))}
        self.groups = list(GROUPS)
        if log.n > 881 and (t == "MDN").any():                 # AV1: the sour branch (13 DC4 ORNs, their 9 relays, 4 MDN) = neurons 881 ..
            self.members["DC4 sour"] = (idx >= 881) & (t != "MDN")
            self.members["MDN back up"] = t == "MDN"
            self.groups += AV1_GROUPS
        col = np.tile(np.array(OTHER, np.float32), (log.n, 1))
        for name, _, c, _ in self.groups:
            col[self.members[name]] = c
        self.col = col
        self.rad = np.where(np.isin(t, ["DNp01", "TTMn", "DNp09", "DNa01", "DNa02"]), 1.8, 1.0)
        hs = log.hs
        self.nmax = np.maximum(hs.max(0), 0.02)                      # per-neuron run maximum: brightness = rate / its own maximum (the old tool normalised each group the same way)
        self.vmembers = dict(self.members, ORN=np.char.startswith(t.astype("U"), "ORN") & (t != "ORN_DC4"), **({"DC4 sour": t == "ORN_DC4"} if "DC4 sour" in self.members else {}))      # the index value / bar of the ORN row counts the receptor neurons only (not the smell-path relays that share the colour)
        self.gmax = {g: max(float(hs[:, m].mean(1).max()), 1e-9) for g, m in self.vmembers.items()}
        self.static = self._text_static()

    def _text_static(self):
        img = Image.new("RGB", (LEFT_W, H), BG)
        return img

    def glow(self, k):
        lg = self.log
        a = np.clip(lg.hs[k] / self.nmax, 0, 1) ** 0.7
        b = 0.28 + 0.72 * a
        layer = np.zeros((H, LEFT_W, 3), np.float32)
        for i in np.argsort(b):
            r = self.rad[i] * (1 + 0.5 * a[i])
            cv2.circle(layer, (int(round(self.xy[i, 0])), int(round(self.xy[i, 1]))), max(1, int(round(r))), tuple(float(v) * b[i] for v in self.col[i]), -1, cv2.LINE_AA)
        out = self.bg + layer + cv2.GaussianBlur(layer, (0, 0), 2.5) * 1.2                        # glow: additive + soft halo
        return np.clip(out, 0, 255).astype(np.uint8)

    def draw(self, k):
        lg = self.log
        d = lg.df.iloc[k]
        pil = Image.fromarray(self.glow(k))
        dr = ImageDraw.Draw(pil)
        x = COL_X
        y = 574
        dr.text((x, y), "LIVE BRAIN", font=font(22, True), fill=(255, 255, 255))
        right = f"{lg.tag} · frame {k}" if getattr(lg, "tag", None) else f"arm {lg.arm} · frame {k}"
        dr.text((x + COL_W, y + 4), right, font=font(16), fill=DIM, anchor="ra")
        dr.text((x, y + 34), f"{lg.n} neurons at their real somas  ·  MaleCNS v1.0", font=font(16), fill=TXT)
        # the active drives: names lit when on
        cx = x
        dr.text((cx, y + 58), "drives:", font=font(16), fill=DIM)
        cx += 66
        for nm in ("looming", "home", "hum", "smell") + (("sour",) if "sour" in lg.toggles else ()):
            on = lg.drive_on(nm)
            dr.text((cx, y + 58), nm, font=font(16, on), fill=(255, 255, 255) if on else (80, 80, 76))
            cx += int(dr.textlength(nm, font=font(16, on))) + 22
        # the buttons pressed
        cx = x
        dr.text((cx, y + 82), "buttons:", font=font(16), fill=DIM)
        cx += 82
        for nm, on in (("→", bool(d.right)), ("←", bool(d.left)), ("A", bool(d.a))):
            dr.text((cx, y + 82), nm, font=font(18, on), fill=(255, 255, 255) if on else (80, 80, 76))
            cx += 34
        dr.text((x, y + 106), "brightness = activity", font=font(16), fill=DIM)
        dr.text((x, y + 128), "JO/ORN at their brain terminals (cell bodies in the antenna)", font=font(16), fill=DIM)
        # the INDEX: dot, name, role, activity bar, value; rows of drives that are off are dimmed
        wide = len(self.groups) > len(GROUPS)                  # AV1: two more rows: tighter pitch, the role column moves right
        yy, pitch, rx = (746, 26, 172) if wide else (768, 30, 108)
        for name, role, c, drives in self.groups:
            on = any(lg.drive_on(dv) for dv in drives)
            f = 1.0 if on else 0.28
            cc = tuple(int(v * f) for v in c)
            tc = tuple(int(v * f) for v in TXT)
            m = self.vmembers[name]
            val = float(lg.hs[k, m].mean())
            a = float(np.clip(val / self.gmax[name], 0, 1))
            dr.ellipse([x, yy + 5, x + 12, yy + 17], fill=cc)
            dr.text((x + 24, yy), name, font=font(18, True), fill=tc)
            dr.text((x + rx, yy), role, font=font(18), fill=tc)
            dr.rectangle([x + 330, yy + 5, x + 450, yy + 17], outline=(52, 52, 50))
            if a > 0:
                dr.rectangle([x + 330, yy + 5, x + 330 + int(120 * a), yy + 17], fill=cc)
            dr.text((x + COL_W, yy), f"{val:7.3f}", font=font(18), fill=tc, anchor="ra")
            yy += pitch
        return np.asarray(pil)


# ------------------------------------------------------------------------------------------------ the game panel
def parse_box(s):
    if not isinstance(s, str) or not s:
        return None
    return tuple(int(v) for v in s.split())


def dotted_rect(img, p0, p1, color, th):
    dashed_rect(img, p0, p1, color, th, dash=4, gap=6)


def dashed_rect(img, p0, p1, color, th, dash=14, gap=10):
    (x0, y0), (x1, y1) = p0, p1
    for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        L = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        for t0 in range(0, L, dash + gap):
            t1 = min(t0 + dash, L)
            q0 = (int(a[0] + (b[0] - a[0]) * t0 / L), int(a[1] + (b[1] - a[1]) * t0 / L))
            q1 = (int(a[0] + (b[0] - a[0]) * t1 / L), int(a[1] + (b[1] - a[1]) * t1 / L))
            cv2.line(img, q0, q1, color, th, cv2.LINE_AA)


def behind_tick(img, x, y, color, label="behind"):
    """RE2: a small left-pointing triangle + 'behind' beside a box whose object is behind Mario (x, y = the anchor, in image px)."""
    cv2.fillPoly(img, [np.array([[x, y], [x + 16, y - 9], [x + 16, y + 9]], np.int32)], color, cv2.LINE_AA)
    cv2.putText(img, label, (x + 22, y + 7), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)


def game_panel(frame, log, k, scale=4):
    """NES x4 = 1024 x 960 with only the overlay: red loom boxes (pit base thin), green hum line, green smell box, and the home dot at the right edge inside the frame at eye height."""
    img = cv2.resize(np.ascontiguousarray(frame), None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST).copy()
    r = log.df.iloc[k]
    sl = float(log.sl_pre[k])
    sx = lambda wx: int(round((wx - sl) * scale))
    sy = lambda ty: int(round((ty + 32) * scale))
    box = parse_box(r.box_x_top_w_h)
    hf = r.get("headroom_factor", 1.0)
    suppressed = (not pd.isna(hf)) and hf < 1.0                      # AV1: the loom of this enemy is scaled down by the headroom factor: its box is DASHED red
    if box and r.threat != "none":
        bx, top, bw, bh = box
        if suppressed:
            dashed_rect(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 4)
        else:
            cv2.rectangle(img, (sx(bx), sy(top)), (sx(bx + bw), sy(top + bh)), RED, 4, cv2.LINE_AA)
        if r.get("threat_rear", 0) == 1:                              # RE2: the loom threat is an enemy BEHIND him
            behind_tick(img, sx(bx + bw) + 14, sy(top) - 16, RED)
    sbox = parse_box(r.get("sour_box_x_top_w_h", ""))
    if sbox:                                                          # the enemy that smells sour: a DOTTED yellow box 4 px outside its red loom box (the loom line is 4 px thick), opacity ~ the sour level
        bx, top, bw, bh = sbox
        lvl = r.get("sour_level", 0.0)
        alpha = float(np.clip((0.0 if pd.isna(lvl) else lvl) / 12.0, 0.25, 1.0))
        ov = img.copy()
        m = 8                                                          # 4 px loom half-thickness + 4 px gap
        dotted_rect(ov, (sx(bx) - m, sy(top) - m), (sx(bx + bw) + m, sy(top + bh) + m), YELLOW, 3)
        img = cv2.addWeighted(ov, alpha, img, 1 - alpha, 0)
        if r.get("sour_rear", 0) == 1:                                # RE2: the sour source is an enemy BEHIND him
            behind_tick(img, sx(bx + bw) + 14, sy(top + bh) + 26, YELLOW)
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
    if log.toggles["home"]:
        eye = log.feet_pre[k] - (24 if log.pow_pre[k] >= 1 else 16)
        ov = img.copy()
        cv2.circle(ov, (img.shape[1] - 22, sy(eye)), 11, WHITE, -1, cv2.LINE_AA)
        a = min(1.0, log.kn.HOME_R)
        img = cv2.addWeighted(ov, a, img, 1 - a, 0)
    return img


# ------------------------------------------------------------------------------------------------ the whole frame
class Renderer:
    stateful = False                       # the panels carry no state between frames: stills / jumps can render any frame directly

    def __init__(self, log, label=None):
        self.log = log
        self.brain = BrainPanel(log)

    def frame(self, nes_frame, k):
        out = np.zeros((H, W, 3), np.uint8)
        out[:] = BG
        out[:, :LEFT_W] = self.brain.draw(k)
        out[GAME_Y:GAME_Y + GAME_H, GAME_X:GAME_X + GAME_W] = game_panel(nes_frame, self.log, k)
        return out


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
        cx, cy = 120 + (j % 2) * 500, 486 + (j // 2) * 44
        dr.ellipse([cx, cy + 8, cx + 14, cy + 22], fill=ORANGE)
        dr.text((cx + 28, cy), f"{a}  {b}", font=font(26), fill=TXT)
    dr.text((1240, 270), "colour language (the index on the left)", font=font(30), fill=TXT)
    for j, (name, role, c, _) in enumerate(GROUPS):
        y = 326 + j * 46
        dr.ellipse([1240, y + 8, 1260, y + 28], fill=c)
        dr.text((1280, y), f"{name}  {role}", font=font(26), fill=TXT)
    dr.text((1240, 800), "game overlay: red = danger (looming), green = pleasant (hum, smell),", font=font(24), fill=DIM)
    dr.text((1240, 836), "yellow = sour (dotted box), white = home (dot): read from RAM", font=font(24), fill=DIM)
    img.save(path)
    return path
