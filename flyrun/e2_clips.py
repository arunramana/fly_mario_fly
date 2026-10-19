"""E2 clips (R3 layout, renderer only). The logs come from the search (`runs/E2_E2_gen<NN>_best.*`, 1-1 noop 0 sigma 0).
python -m flyrun.e2_clips best_full   -> clips/E2_best_full.mp4
python -m flyrun.e2_clips vs          -> clips/E2_vs_E1s.mp4      side by side on a test episode where E2 dies and E1s passes (the hard set), ~10 s, 0.5x
python -m flyrun.e2_clips geometry    -> clips/E2_geometry.png    the old vs the evolved pit tower / hum reach / eye point on a frame at pit 1
python -m flyrun.e2_clips opening12   -> clips/E2_12_opening.mp4  the E2 best on the 1-2 opening (information only)"""
import json
import os
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == "opening12":
    os.environ["FLYRUN_LEVEL"] = "1-2"

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

from . import e1s_genome as S
from . import e2_genome as G
from . import e1s_clips as EC
from .render import panels as P
from .render.panels import Log, Renderer, font, game_panel
from .render.video import replay

ROOT = Path(__file__).resolve().parent
RUNS, CLIPS = ROOT / "runs", ROOT / "clips"


def best():
    prog = json.load(open(RUNS / "E2_progress.json"))
    g = prog["best"]["gen"]
    return g, prog["best"], str(RUNS / f"E2_E2_gen{g:02d}_best")


def main_best_full():
    g, b, base = best()
    lg = Log(base, brain=EC.brain(G.WFILE, G.BODIES))
    lg.arm, lg.tag = "E2 best", f"E2 best (generation {g})"
    rd = Renderer(lg)
    EC.write((rd.frame(nes, k) for k, nes in replay(lg)), CLIPS / "E2_best_full.mp4")


def main_vs():
    from . import e1s_log
    T = json.load(open(RUNS / "E2_test.json"))
    R = T["result"]
    cand = [(i, ep) for i, ep in enumerate(T["hard_set"]) if R["E2"]["hard"][i]["max_x"] > 100 and not R["E2"]["hard"][i]["flag"] and R["E1s"]["hard"][i]["flag"]]
    i, ep = cand[0]
    e2 = best()[1]["values"]
    e1s = json.load(open(RUNS / "E1s_progress.json"))["best"]["values"]
    epd = dict(noop_start=ep["noop_start"], seed=ep["seed"], sigma=ep["sigma"])
    b907 = EC.brain(G.WFILE, G.BODIES)
    base2, s2 = e1s_log.log_run(e2, "vs_e2", ep=epd, brain=b907, prefix="E2", knobs_fn=G.knobs_for)
    base1, s1 = e1s_log.log_run(e1s, "vs_e1s", ep=epd, brain=b907, prefix="E2", knobs_fn=G.knobs_for)
    print("episode", epd, "E2:", s2["max_x"], s2["end_reason"], s2["cause"], "| E1s:", s1["max_x"], s1["end_reason"])
    x0 = max(0, int(s2["max_x"]) - 130)
    ho1 = sum(r["flag"] for r in T["result"]["E1s"]["holdout"])
    ho2 = sum(r["flag"] for r in T["result"]["E2"]["holdout"])
    specs = [(f"E2 best (generation {best()[0]})", f"fitness {best()[1]['fitness']:.3f} · HOLDOUT {ho2}/10", str(base2), b907, float(e2["TTMN_THRESH"])),
             ("E1s best (generation 8)", f"fitness 1.171 · HOLDOUT {ho1}/10", str(base1), b907, float(e1s["TTMN_THRESH"]))]
    sb = EC.SideBySide2(specs, x0)
    EC.write((sb.frame(j) for j in range(sb.n)), CLIPS / "E2_vs_E1s.mp4")


def main_geometry():
    """The old rule vs the evolved choices on one frame: pit tower, hum reach, eye point."""
    g, b, base = best()
    v = b["values"]
    lg = Log(base, brain=EC.brain(G.WFILE, G.BODIES))
    k0 = int(np.argmax(lg.df.x.to_numpy() >= 1045))
    from . import level
    from .env import mario_x
    from .run import _get_env
    from .senses_v2 import MAX_JUMP_HEIGHT, rim_top
    for k, nes in replay(lg, k0):
        if k == k0:
            ram = _get_env().unwrapped.ram
            walls, pits = level.scan_visible(ram, rim=True)
            frame, mx, feet = nes, mario_x(ram), int(ram[0xCE])
            blocks = level.scan_blocks(ram)
    px, pw = next(p for p in pits if p[0] >= mx)
    near_y, far_y = rim_top(walls, px - 16), rim_top(walls, px + pw)
    base_y = min(near_y, far_y)
    img = game_panel(frame, lg, k0)
    sl = float(lg.sl_pre[k0])
    sx = lambda wx: int(round((wx - sl) * 4))
    sy = lambda ty: int(round((ty + 32) * 4))

    def box(x, top, w, h, col, th, dashed=False):
        p0, p1 = (sx(x), sy(top)), (sx(x + w), sy(top + h))
        (P.dashed_rect(img, p0, p1, col, th, 12, 8) if dashed else cv2.rectangle(img, p0, p1, col, th, cv2.LINE_AA))
    ORANGE = (255, 150, 40)
    old_top = base_y - min(pw, MAX_JUMP_HEIGHT)
    new_top = base_y - min(pw, MAX_JUMP_HEIGHT) * v["PIT_TOWER_H"]
    old_x, new_x = px + pw, px + int(round(v["PIT_TOWER_POS"] * pw))
    box(old_x, old_top, 16, base_y - old_top, (240, 240, 240), 4, dashed=True)                         # the rule: far edge, height W
    box(new_x, new_top, 16, base_y - new_top, ORANGE, 4)                                               # E2: position and height evolved
    ground = level.ROW_GROUND * 16
    for reach, col, dash in ((64.0, (240, 240, 240), True), (v["HUM_REACH_PX"], ORANGE, False)):        # hum reach: blocks whose underside is lower than this line hum
        y = sy(ground - reach)
        if dash:
            for xx in range(0, img.shape[1], 24):
                cv2.line(img, (xx, y), (xx + 12, y), col, 2)
        else:
            cv2.line(img, (0, y), (img.shape[1], y), col, 2)
    ex = sx(mx + 12)
    cv2.circle(img, (ex, sy(feet - 16)), 9, (240, 240, 240), 2, cv2.LINE_AA)                            # the eye point: the top-front corner (rule)
    cv2.circle(img, (ex, sy(feet - 16 + v["EYE_DY"])), 9, ORANGE, -1, cv2.LINE_AA)                      # E2: lowered
    pil = Image.fromarray(img)
    dr = ImageDraw.Draw(pil)
    pil2 = Image.new("RGB", (1024, 960 + 150), P.BG)
    pil2.paste(pil, (0, 0))
    dr = ImageDraw.Draw(pil2)
    dr.text((20, 975), "white dashed = the rule      orange = E2 evolved", font=font(26, True), fill=(240, 240, 240))
    dr.text((20, 1015), f"pit tower: position {v['PIT_TOWER_POS']:.2f} along the pit (rule 1.00), height x{v['PIT_TOWER_H']:.2f} (rule x1.00)", font=font(22), fill=(205, 204, 196))
    dr.text((20, 1048), f"hum reach: {v['HUM_REACH_PX']:.0f} px (rule 64)      eye point lowered by {v['EYE_DY']:.1f} px (rule 0)", font=font(22), fill=(205, 204, 196))
    dr.text((20, 1081), "(frame: E2 best, 1-1, just before pit 1; the hum reach lines are drawn across the screen)", font=font(18), fill=(130, 130, 124))
    pil2.save(CLIPS / "E2_geometry.png")
    print("E2_geometry.png", pil2.size, "pit", px, pw, "old tower top", old_top, "new top", round(new_top, 1), "old x", old_x, "new x", new_x)


def main_opening12():
    from . import e1s_log
    g, b, _ = best()
    base, s = e1s_log.log_run(b["values"], "12opening", prefix="E2", knobs_fn=G.knobs_for)
    print("1-2 opening:", {k: s[k] for k in ("max_x", "end_reason", "cause", "frames", "score")})
    lg = Log(str(base), brain=EC.brain(G.WFILE, G.BODIES))
    lg.arm, lg.tag = "E2 best on 1-2", "E2 best, World 1-2 opening"
    rd = Renderer(lg)
    EC.write((rd.frame(nes, k) for k, nes in replay(lg)), CLIPS / "E2_12_opening.mp4")


if __name__ == "__main__":
    {"best_full": main_best_full, "vs": main_vs, "geometry": main_geometry, "opening12": main_opening12}[sys.argv[1]]()
