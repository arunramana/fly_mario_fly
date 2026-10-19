"""E1s clips (R3 layout, renderer only). The logs come from the search (`runs/E1s_E1s_gen<NN>_best.*`, the best genome of each generation, 1-1 noop 0 sigma 0).
python -m flyrun.e1s_clips best_full     -> clips/E1s_best_full.mp4        the best genome, 1-1 noop 0 sigma 0, the whole run
python -m flyrun.e1s_clips vs_e1         -> clips/E1s_vs_E1.mp4            side by side, E1 best vs E1s best, ~10 s around the first back-up moment (0.5x)
python -m flyrun.e1s_clips backups       -> clips/E1s_backup_moments.mp4   <= 20 s montage of 3-4 back-up moments
python -m flyrun.e1s_clips opening12     -> clips/E1s_12_opening.mp4       the best genome on the 1-2 opening (noop 0, sigma 0), information only"""
import json
import os
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == "opening12":
    os.environ["FLYRUN_LEVEL"] = "1-2"          # must be set before the first emulator use

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from . import c1_run as C
from . import e1s_genome as G
from .render import montage as M
from .render import panels as P
from .render import progress as PR
from .render.panels import Log, Renderer, font, game_panel
from .render.video import replay

ROOT = Path(__file__).resolve().parent
RUNS, CLIPS = ROOT / "runs", ROOT / "clips"
W, H, BG = P.W, P.H, P.BG
FPS = 60


def brain(wfile, bodies):
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, bodies
    from .brain import load_brain
    return load_brain()


def best():
    prog = json.load(open(RUNS / "E1s_progress.json"))
    g = prog["best"]["gen"]
    return g, prog["best"], str(RUNS / f"E1s_E1s_gen{g:02d}_best")


def e1s_log(base=None):
    g, b, base0 = best()
    return Log(base or base0, brain=brain(G.WFILE, G.BODIES))


def write(frames_iter, path):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    n = 0
    for img in frames_iter:
        vw.write(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        n += 1
    vw.release()
    print(Path(path).name, n, "frames = %.1f s" % (n / FPS))


# ------------------------------------------------------------------------------------------------ best_full
def main_best_full():
    lg = e1s_log()
    lg.arm = "E1s best"
    lg.tag = f"E1s best (generation {best()[0]})"
    rd = Renderer(lg)
    write((rd.frame(nes, k) for k, nes in replay(lg)), CLIPS / "E1s_best_full.mp4")


# ------------------------------------------------------------------------------------------------ side by side
class SideBySide2(PR.SideBySide):
    """The V1 side by side with two arbitrary logs (each with its own brain), aligned by x, 0.5x, the TTMn jump threshold ticks, and a yellow 'BACKING UP' note under a game."""

    def __init__(self, specs, x0, n=300):
        self.n = n * 2
        self.sides = []
        for label, sub, base, brain_, thr in specs:
            lg = Log(base, brain=brain_)
            lg.arm = label
            k0 = int(np.argmax(lg.df.x.to_numpy() >= x0))
            frames = []
            for k, nes in replay(lg, min(len(lg) - 1, k0 + n - 1)):
                if k >= k0:
                    frames.append((k, nes))
            br = lg.brain
            t = br.bodies.type.astype(str).to_numpy()
            side = br.bodies.somaSide.astype(str).to_numpy()
            members = {"LC4": t == "LC4", "LPLC2": t == "LPLC2", "DNp01": t == "DNp01", "TTMn": t == "TTMn", "DNa L": np.isin(t, ["DNa01", "DNa02"]) & (side == "L"),
                       "DNa R": np.isin(t, ["DNa01", "DNa02"]) & (side == "R"), "DNp09": t == "DNp09", "LC10a": t == "LC10a", "JO": np.char.startswith(t.astype("U"), "JO"),
                       "ORN": np.char.startswith(t.astype("U"), "ORN") & (t != "ORN_DC4")}
            self.sides.append(dict(label=label, sub=sub, lg=lg, frames=frames, thr=thr, members=members))
        self.gmax = {g: max(float(s["lg"].hs[:, s["members"][g]].mean(1).max()) for s in self.sides) + 1e-9 for g, *_ in P.GROUPS}

    def frame(self, i):
        img = super().frame(i)
        pil = Image.fromarray(img)
        dr = ImageDraw.Draw(pil)
        for side, gx in zip(self.sides, self.GX):
            j = min(i // 2, len(side["frames"]) - 1)
            k = side["frames"][j][0]
            d = side["lg"].df.iloc[k]
            if "backup" in side["lg"].df and int(d.backup) == 1:
                dr.rectangle([gx + 20, 940, gx + 330, 980], fill=(60, 52, 8))
                dr.text((gx + 30, 960), f"BACKING UP · MDN {float(d.mdn):.2f}", font=font(24, True), fill=(250, 215, 60), anchor="lm")
        return np.asarray(pil)


def main_vs_e1():
    g, b, base = best()
    ho = json.load(open(RUNS / "E1s_holdout.json"))["episodes"]
    e1 = json.load(open(RUNS / "E1_progress.json"))
    d = pd.read_csv(base + ".csv")
    bk = np.flatnonzero(d.backup.to_numpy() == 1)
    first = int(bk[0]) if len(bk) else int(len(d) // 3)
    x0 = max(0, int(d.x.iloc[first]) - 90)
    b881 = brain("W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet")
    b907 = brain(G.WFILE, G.BODIES)
    e1_thr = float(e1["best"]["values"]["TTMN_THRESH"])
    s_thr = float(b["values"]["TTMN_THRESH"])
    specs = [("E1 best (generation 6)", f"fitness {e1['best']['fitness']:.3f} · HOLDOUT 8/10 flags", str(RUNS / "E1_E1_gen06_best"), b881, e1_thr),
             (f"E1s best (generation {g})", f"fitness {b['fitness']:.3f} · HOLDOUT {sum(r['flag'] for r in ho)}/10 flags", base, b907, s_thr)]
    sb = SideBySide2(specs, x0)
    sb.sides[0]["lg"].tag = "E1"
    write((sb.frame(i) for i in range(sb.n)), CLIPS / "E1s_vs_E1.mp4")
    print("x0", x0, "first back-up frame", first, "x", int(d.x.iloc[first]))


# ------------------------------------------------------------------------------------------------ back-up moments
def bursts(df):
    bk = df.backup.to_numpy()
    out, k = [], 0
    while k < len(bk):
        if bk[k]:
            j = k
            while j < len(bk) and bk[j]:
                j += 1
            out.append((k, j - k))
            k = j
        else:
            k += 1
    return out


def main_backups(n_clips=4, pre=90, length=270):
    lg = e1s_log()
    lg.arm, lg.tag = "E1s best", f"E1s best (generation {best()[0]})"
    bs = bursts(lg.df)
    # spread the moments over the level: take bursts at least 150 px apart, the longer ones first, at most n_clips, shown in order of x
    chosen = []
    for k, ln in sorted(bs, key=lambda t: -t[1]):
        x = int(lg.df.x.iloc[k])
        if all(abs(x - cx) > 150 for _, cx in chosen):
            chosen.append((k, x))
        if len(chosen) == n_clips:
            break
    chosen.sort(key=lambda t: t[1])
    print("back-up bursts:", len(bs), "chosen (frame, x):", chosen)
    rd = Renderer(lg)
    wanted = [(max(0, k - pre), max(0, k - pre) + length) for k, _ in chosen]
    last = max(e for _, e in wanted)

    def frames():
        for k, nes in replay(lg, min(len(lg) - 1, last)):
            for s, e in wanted:
                if s <= k < e:
                    d = lg.df.iloc[k]
                    txt = f"x {int(d.x)} · MDN {float(d.mdn):.2f} · sour θ {float(d.sour_theta_deg):.0f}°"
                    yield M.caption(rd.frame(nes, k), txt), s
    # the replay yields frames in time order, one clip's frames after the other
    write((img for img, _ in frames()), CLIPS / "E1s_backup_moments.mp4")


# ------------------------------------------------------------------------------------------------ 1-2 opening
def main_opening12():
    from . import e1s_log
    g, b, _ = best()
    base, s = e1s_log.log_run(b["values"], "12opening", prefix="E1s")
    print("1-2 opening:", {k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "score")})
    lg = Log(str(base), brain=brain(G.WFILE, G.BODIES))
    lg.arm, lg.tag = "E1s best on 1-2", "E1s best, World 1-2 opening"
    rd = Renderer(lg)
    write((rd.frame(nes, k) for k, nes in replay(lg)), CLIPS / "E1s_12_opening.mp4")


if __name__ == "__main__":
    {"best_full": main_best_full, "vs_e1": main_vs_e1, "backups": main_backups, "opening12": main_opening12}[sys.argv[1]]()
