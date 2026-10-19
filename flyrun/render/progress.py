"""V1 (revised plan): two clips + the end card.
 clips/V1_start_vs_evolved.mp4: side by side, the START genome (arm C, dies at x 1220) vs the E1 best (generation 6), noop 0 sigma 0, the same x window (both from x >= 1000), ~10 s; two game panels (NES x3)
   with a caption on each side and ONE shared brain index in the middle (two bars per row: start | evolved).
 clips/V1_progress.mp4 (<= 25 s): the fitness-per-generation strip (best + mean, E1 logs), 3 short cuts of the generations where something new appears (each captioned "generation N · score S"), the end card.
python -m flyrun.render.progress stills   -> clips/V1_stills/V1_sbs.png, V1_progress_strip.png, V1_progress_cut.png
python -m flyrun.render.progress render   -> the two mp4 (only after approval)"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from . import panels as P
from . import montage as M
from .panels import GROUPS, Log, BrainPanel, font, game_panel
from .video import replay

ROOT = Path(__file__).resolve().parents[1]
RUNS, CLIPS = ROOT / "runs", ROOT / "clips"
W, H, BG = P.W, P.H, P.BG
FPS = 60


# ------------------------------------------------------------------------------------------------ side by side
def window_frames(base, x0=1000, n=300):
    """-> (Log, [(k, NES frame)]) for the frames from the first frame with x >= x0 on, up to n frames (fewer if the run ends first)."""
    lg = Log(base)
    k0 = int(np.argmax(lg.df.x.to_numpy() >= x0))
    out = []
    for k, nes in replay(lg, min(len(lg) - 1, k0 + n - 1)):
        if k >= k0:
            out.append((k, nes))
    return lg, out


class SideBySide:
    GX = (0, 1152)                                 # left edges of the two game panels (NES x3 = 768 x 720); the middle 384 px is the shared index
    GY, SC = 150, 3

    def __init__(self, n=300):
        self.n = n * 2                                      # video frames (each game frame twice)
        prog = json.load(open(RUNS / "E1_progress.json"))
        start = json.load(open(RUNS / "E1_start.json"))["start"]
        self.sides = []
        for label, base, sub in (("START genome (arm C)", str(RUNS / "R1_armC"), f"fitness {start['fitness']:.3f} · flags on training {start['flags']}/12"),
                                 ("EVOLVED (E1 best, generation 6)", str(RUNS / "E1_E1_gen06_best"), f"fitness {prog['best']['fitness']:.3f} · flags on training 12/12")):
            lg, frames = window_frames(base, n=n)
            self.sides.append(dict(label=label, sub=sub, lg=lg, frames=frames))
        self.members = {}
        bp = BrainPanel.__new__(BrainPanel)                      # only the group membership is needed (no positions): rebuild it the same way
        for s in self.sides:
            br = s["lg"].brain
            t = br.bodies.type.astype(str).to_numpy()
            side = br.bodies.somaSide.astype(str).to_numpy()
            idx = np.arange(s["lg"].n)
            s["members"] = {"LC4": t == "LC4", "LPLC2": t == "LPLC2", "DNp01": t == "DNp01", "TTMn": t == "TTMn", "DNa L": np.isin(t, ["DNa01", "DNa02"]) & (side == "L"),
                            "DNa R": np.isin(t, ["DNa01", "DNa02"]) & (side == "R"), "DNp09": t == "DNp09", "LC10a": t == "LC10a", "JO": np.char.startswith(t.astype("U"), "JO"),
                            "ORN": np.char.startswith(t.astype("U"), "ORN")}
        self.gmax = {g: max(float(s["lg"].hs[:, s["members"][g]].mean(1).max()) for s in self.sides) + 1e-9 for g, *_ in GROUPS}

    def frame(self, i):
        img = Image.new("RGB", (W, H), BG)
        arr = np.asarray(img).copy()
        info = []
        for side, gx in zip(self.sides, self.GX):
            g = i // 2                                   # slow motion: every game frame is shown twice (0.5x)
            j = min(g, len(side["frames"]) - 1)
            k, nes = side["frames"][j]
            lg = side["lg"]
            arr[self.GY:self.GY + 720, gx:gx + 768] = game_panel(nes, lg, k, scale=self.SC)
            info.append((k, j, g > j))
        pil = Image.fromarray(arr)
        dr = ImageDraw.Draw(pil)
        for side, gx, (k, j, dead) in zip(self.sides, self.GX, info):
            lg = side["lg"]
            dr.text((gx + 20, 50), side["label"], font=font(34, True), fill=(255, 255, 255), anchor="lm")
            dr.text((gx + 20, 100), side["sub"], font=font(24), fill=(170, 170, 165), anchor="lm")
            d = lg.df.iloc[k]
            dr.text((gx + 20, 905), f"x {int(d.x)} · score {int(d.score)}", font=font(28), fill=(235, 235, 235), anchor="lm")
            if dead:
                dr.rectangle([gx + 120, self.GY + 280, gx + 648, self.GY + 440], fill=(120, 14, 14))
                dr.text((gx + 384, self.GY + 360), f"DIED at x {int(lg.df.x.iloc[-1])}", font=font(46, True), fill=(255, 255, 255), anchor="mm")
        dr.text((W // 2, 1000), "0.5x speed · both from x 1000 · same game frames", font=font(22), fill=(150, 150, 145), anchor="mm")
        # the shared index: group, two bars (start | evolved), the two values
        x0 = 790
        dr.text((768 + 192, 150), "brain activity", font=font(22, True), fill=(205, 204, 196), anchor="mt")
        dr.text((x0 + 4, 186), "start", font=font(18), fill=(150, 150, 145))
        dr.text((x0 + 190, 186), "evolved", font=font(18), fill=(150, 150, 145))
        y = 216
        for name, role, c, drives in GROUPS:
            dr.ellipse([x0 - 22, y + 4, x0 - 10, y + 16], fill=c)
            dr.text((x0, y), name, font=font(18, True), fill=(205, 204, 196))
            vals = []
            for si, side in enumerate(self.sides):
                k = info[si][0]
                lg = side["lg"]
                v = float(lg.hs[k, side["members"][name]].mean())
                vals.append(v)
                bx = x0 + si * 186
                dr.rectangle([bx, y + 26, bx + 150, y + 36], outline=(52, 52, 50))
                a = float(np.clip(v / self.gmax[name], 0, 1))
                if a > 0:
                    dr.rectangle([bx, y + 26, bx + int(150 * a), y + 36], fill=c)
            dr.text((x0 + 96, y), f"{vals[0]:.2f}", font=font(18), fill=(150, 150, 145))
            dr.text((x0 + 96 + 186, y), f"{vals[1]:.2f}", font=font(18), fill=(205, 204, 196))
            y += 62
        return np.asarray(pil)

    def __len__(self):
        return self.n


# ------------------------------------------------------------------------------------------------ the fitness strip
def strip_frame(progress, start_fit, f, total=240):
    """Frame f of the strip: best (red) and mean (white) fitness per generation, drawn up to generation (f / total) * 14."""
    rows = progress["rows"]
    n = len(rows)
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)
    dr.text((W // 2, 80), "fitness per generation (mean of the 12 training episodes)", font=font(44, True), fill=(255, 255, 255), anchor="mm")
    X0, X1, Y0, Y1 = 200, 1760, 200, 900
    ymax = 1.4
    xs = lambda g: X0 + (X1 - X0) * g / (n - 1)
    ys = lambda v: Y1 - (Y1 - Y0) * (v + 0.2) / (ymax + 0.2)
    dr.rectangle([X0, Y0, X1, Y1], outline=(60, 62, 70), width=2)
    for v in (0, 0.5, 1.0):
        dr.line([(X0, ys(v)), (X1, ys(v))], fill=(40, 42, 50), width=1)
        dr.text((X0 - 14, ys(v)), f"{v:.1f}", font=font(24), fill=(190, 190, 185), anchor="rm")
    for g in range(0, n, 2):
        dr.text((xs(g), Y1 + 14), str(g), font=font(24), fill=(190, 190, 185), anchor="mt")
    dr.text((W // 2, Y1 + 56), "generation", font=font(26), fill=(190, 190, 185), anchor="mt")
    dr.line([(X0, ys(start_fit)), (X1, ys(start_fit))], fill=(255, 210, 74), width=2)
    dr.text((X1 - 8, ys(start_fit) + 10), f"start genome {start_fit:.3f}", font=font(26), fill=(255, 210, 74), anchor="ra")
    reveal = min(n - 1, (n - 1) * min(1.0, f / total))
    for key, col, lab in (("mean", (235, 235, 235), "population mean"), ("best", (255, 90, 74), "best of the generation")):
        pts = []
        for g in range(n):
            if g <= reveal:
                pts.append((xs(g), ys(rows[g][key])))
        if reveal < n - 1:
            g0 = int(reveal)
            frac = reveal - g0
            v = rows[g0][key] + frac * (rows[g0 + 1][key] - rows[g0][key])
            pts.append((xs(reveal), ys(v)))
        if len(pts) > 1:
            dr.line(pts, fill=col, width=5)
        for p in pts[:-1] if reveal < n - 1 else pts:
            dr.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=col)
    dr.rectangle([X0 + 20, Y0 + 20, X0 + 360, Y0 + 100], fill=(14, 16, 22))
    dr.line([(X0 + 36, Y0 + 40), (X0 + 76, Y0 + 40)], fill=(255, 90, 74), width=5)
    dr.text((X0 + 90, Y0 + 40), "best of the generation", font=font(24), fill=(235, 235, 235), anchor="lm")
    dr.line([(X0 + 36, Y0 + 78), (X0 + 76, Y0 + 78)], fill=(235, 235, 235), width=5)
    dr.text((X0 + 90, Y0 + 78), "population mean", font=font(24), fill=(235, 235, 235), anchor="lm")
    if f >= total:
        dr.text((xs(n - 1) - 10, ys(rows[-1]["best"]) - 30), f"best {max(r['best'] for r in rows):.3f}", font=font(28, True), fill=(255, 90, 74), anchor="rm")
    return np.asarray(img)


# ------------------------------------------------------------------------------------------------ the cuts
CUTS = [(0, 300, "first mushroom eaten"), (3, 740, "4 blocks hit, mushroom at x 1248"), (10, 1130, "best score")]


def cut_frames(gen, k0, note, n=300):
    prog = json.load(open(RUNS / "E1_progress.json"))
    base = str(RUNS / f"E1_E1_gen{gen:02d}_best")
    score = int(pd.read_csv(base + ".csv").score.iloc[-1])
    text = f"generation {gen} · score {score} · {note}"
    out = []
    lg = Log(base)
    lg.arm = f"gen{gen:02d}"
    lg.tag = f"generation {gen}"
    rd = P.Renderer(lg)
    for k, nes in replay(lg, k0 + n - 1):
        if k >= k0:
            out.append(M.caption(rd.frame(nes, k), text))
    return out


def main_stills():
    out = CLIPS / "V1_stills"
    out.mkdir(parents=True, exist_ok=True)
    sb = SideBySide(n=300)
    died = len(sb.sides[0]["frames"]) - 1
    i = max(0, 2 * died - 40)
    cv2.imwrite(str(out / "V1_sbs.png"), cv2.cvtColor(sb.frame(i), cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out / "V1_sbs_after_death.png"), cv2.cvtColor(sb.frame(2 * died + 120), cv2.COLOR_RGB2BGR))
    prog = json.load(open(RUNS / "E1_progress.json"))
    start = json.load(open(RUNS / "E1_start.json"))["start"]["fitness"]
    cv2.imwrite(str(out / "V1_progress_strip.png"), cv2.cvtColor(strip_frame(prog, start, 240), cv2.COLOR_RGB2BGR))
    gen, k0, note = CUTS[1]
    fr = cut_frames(gen, k0, note, n=130)
    cv2.imwrite(str(out / "V1_progress_cut.png"), cv2.cvtColor(fr[119], cv2.COLOR_RGB2BGR))      # generation 3, ~2 s in: the mushroom block hit at frame 747 / eaten at 859
    print("sbs: start window frames", len(sb.sides[0]["frames"]), "start dies in window frame", died, "| evolved window frames", len(sb.sides[1]["frames"]))
    print("stills written")


def main_render():
    prog = json.load(open(RUNS / "E1_progress.json"))
    start = json.load(open(RUNS / "E1_start.json"))["start"]["fitness"]
    # 1. side by side
    sb = SideBySide(n=300)
    vw = cv2.VideoWriter(str(CLIPS / "V1_start_vs_evolved.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(600):
        vw.write(cv2.cvtColor(sb.frame(i), cv2.COLOR_RGB2BGR))
    vw.release()
    print("V1_start_vs_evolved.mp4: 600 frames = 10.0 s")
    # 2. progress: strip 5 s, three cuts of 5 s, end card 4 s = 24 s
    vw = cv2.VideoWriter(str(CLIPS / "V1_progress.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    n = 0
    for f in range(300):
        vw.write(cv2.cvtColor(strip_frame(prog, start, min(f, 240)), cv2.COLOR_RGB2BGR))
        n += 1
    for gen, k0, note in CUTS:
        for img in cut_frames(gen, k0, note, n=300):
            vw.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            n += 1
    card = cv2.cvtColor(M.end_card(CLIPS / "V1_genes.png"), cv2.COLOR_RGB2BGR)
    for _ in range(240):
        vw.write(card)
        n += 1
    vw.release()
    print("V1_progress.mp4:", n, "frames = %.1f s" % (n / FPS))


if __name__ == "__main__":
    {"stills": main_stills, "render": main_render}[sys.argv[1]]()
