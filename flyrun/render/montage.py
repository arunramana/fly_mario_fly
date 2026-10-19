"""V1: the evolution montage in the R3 layout. Segments: the START genome (arm C, dies at x 1220), then the best genome of generations 0, 2, 4, ... (each: the last ~5 s of its logged noop 0 sigma 0 run, which is the flag
for every generation), a caption bar at the top of the game column ("generation N · fitness F · flags on training x/12"), and an end card (the E1b finding + each gene over the generations).
python -m flyrun.render.montage stills   -> clips/V1_stills/*.png (2 montage frames + the end card) and clips/V1_genes.png
python -m flyrun.render.montage render   -> clips/V1_evolution_montage.mp4, clips/V1_start_vs_evolved.mp4 (only after approval)"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from . import panels as P
from .panels import Log, Renderer, font
from .video import replay

ROOT = Path(__file__).resolve().parents[1]
RUNS, CLIPS = ROOT / "runs", ROOT / "clips"
WINDOW = 300                                   # frames per segment (5 s at 60 fps)


def segments():
    """[(label, Log base, caption)] : the start genome, then generations 0, 2, 4, ... of E1."""
    prog = json.load(open(RUNS / "E1_progress.json"))
    start = json.load(open(RUNS / "E1_start.json"))["start"]
    segs = [("start", str(RUNS / "R1_armC"), f"start genome (arm C) · fitness {start['fitness']:.3f} · flags on training {start['flags']}/12")]
    for r in prog["rows"]:
        if r["gen"] % 2 == 0:
            segs.append((f"gen{r['gen']:02d}", str(RUNS / f"E1_E1_gen{r['gen']:02d}_best"), f"generation {r['gen']} · fitness {r['best']:.3f} · flags on training {r['best_flags']}/12"))
    return segs


def caption(img, text):
    """A small caption bar across the top band of the game column (the 60 px above the game)."""
    pil = Image.fromarray(img)
    dr = ImageDraw.Draw(pil)
    dr.rectangle([P.GAME_X, 0, P.W, 56], fill=(18, 20, 28))
    dr.text((P.GAME_X + 24, 28), text, font=font(26, True), fill=(235, 235, 235), anchor="lm")
    return np.asarray(pil)


def segment_frames(label, base, text, window=WINDOW, start_at=None):
    """Yield captioned frames of one segment: the last `window` frames of the run (the death at x 1220 for the start genome, the flag for the generations), or from frame start_at."""
    lg = Log(base)
    lg.arm = label
    lg.tag = {"start": "start genome"}.get(label, label.replace("gen", "generation ").replace("generation 0", "generation ") if False else "generation " + str(int(label[3:])) if label.startswith("gen") else label)
    rd = Renderer(lg)
    k0 = max(0, len(lg) - window) if start_at is None else start_at
    for k, nes in replay(lg):
        if k >= k0:
            yield caption(rd.frame(nes, k), text), k


def genes_figure(path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    prog = json.load(open(RUNS / "E1_progress.json"))
    genes = json.load(open(RUNS / "E1_start.json"))["genes"]
    rows = prog["rows"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 16})
    fig, axs = plt.subplots(2, 3, figsize=(18, 8.5), sharex=True, facecolor="#06060a")
    for ax, g in zip(axs.flat, genes):
        ax.set_facecolor("#06060a")
        for r in rows:
            ax.scatter([r["gen"]] * len(r["all_values"]), [v[g["name"]] for v in r["all_values"]], s=14, c="#555a66")
        ax.plot([r["gen"] for r in rows], [r["best_values"][g["name"]] for r in rows], "o-", c="#ff5a4a", ms=5, lw=2)
        ax.axhline(g["start"], c="#dddddd", ls="--", lw=1)
        ax.set_title(g["name"], color="#eeeeee", fontsize=20, fontweight="bold" if g["name"] == "TTMN_THRESH" else "normal")
        if g["log"]:
            ax.set_yscale("log")
            from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
            lo_, hi_ = g["lo"], g["hi"]
            ticks = [round(v, 3 if v < 1 else 1) for v in np.geomspace(lo_, hi_, 4)]
            ax.yaxis.set_major_locator(FixedLocator(ticks))
            ax.yaxis.set_major_formatter(ScalarFormatter())
            ax.yaxis.set_minor_formatter(NullFormatter())
            ax.yaxis.set_minor_locator(FixedLocator([]))
        ax.set_xticks(range(0, 15, 2))
        if g["name"] == "TTMN_THRESH":
            for sp in ax.spines.values():
                sp.set_color("#ffd24a")
                sp.set_linewidth(3)
        if g["name"] != "TTMN_THRESH":
            for sp in ax.spines.values():
                sp.set_color("#555a66")
        ax.tick_params(colors="#cccccc")
    for ax in axs[1]:
        ax.set_xlabel("generation", color="#cccccc")
    fig.suptitle("each gene over the generations   (grey: the population · red: best of the generation · dashed: the start)", color="#cccccc", fontsize=17)
    fig.tight_layout()
    fig.savefig(path, dpi=100, facecolor=fig.get_facecolor())
    plt.close(fig)


def end_card(genes_png):
    img = Image.new("RGB", (P.W, P.H), P.BG)
    dr = ImageDraw.Draw(img)
    dr.text((P.W // 2, 90), "Evolution's key move: jump threshold 0.10 → 0.1275 (+27%)", font=font(52, True), fill=(255, 255, 255), anchor="mm")
    dr.text((P.W // 2, 150), "that one gene takes the start genome from 0/10 to 9/10 flags on HOLDOUT (E1b ablation)", font=font(28), fill=(170, 170, 165), anchor="mm")
    g = Image.open(genes_png).convert("RGB")
    h = 800
    g = g.resize((int(g.width * h / g.height), h), Image.LANCZOS)
    img.paste(g, ((P.W - g.width) // 2, 200))
    return np.asarray(img)


def main_stills():
    out = CLIPS / "V1_stills"
    out.mkdir(parents=True, exist_ok=True)
    genes_figure(CLIPS / "V1_genes.png")
    segs = {s[0]: s for s in segments()}
    for key, name in (("start", "V1_montage_start"), ("gen06", "V1_montage_gen06")):
        label, base, text = segs[key]
        lg = Log(base)
        k = len(lg) - 60 if key == "start" else len(lg) - 10          # start: just before it dies at x 1220; gen 6: the flag
        for img, kk in segment_frames(label, base, text, window=len(lg) - k):
            last = img
            break
        cv2.imwrite(str(out / f"{name}.png"), cv2.cvtColor(last, cv2.COLOR_RGB2BGR))
    cv2.imwrite(str(out / "V1_end_card.png"), cv2.cvtColor(end_card(CLIPS / "V1_genes.png"), cv2.COLOR_RGB2BGR))
    print("stills written", [p.name for p in sorted(out.glob("*.png"))])


if __name__ == "__main__":
    {"stills": main_stills}[sys.argv[1]]()
