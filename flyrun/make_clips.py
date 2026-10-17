"""Part 5 video assets: python -m flyrun.make_clips -> clips/0N_*.mp4, clips/data/*.csv, clips/numbers.md.
Renders only. The episodes are the same deterministic ones the numbers come from. Brain panel = nb 10's
idea (soma x vs z from MaleCNS somaLocation over a faint whole-CNS cloud), drawn with cv2 for speed.
Brightness of a soma = min(1, h / 0.5), one fixed scale for every clip (real and shuffled alike)."""
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .baselines import CONTROLLERS
from .brain import CACHE, Brain, load_brain
from .episodes4 import HOLDOUT
from .evolve4 import EVO4, PART4
from .evolve5 import EVO5
from .genome import BASE, decode
from .run import run_episode

ROOT = Path(__file__).resolve().parent
CLIPS = ROOT / "clips"
DATA = CLIPS / "data"
DISPLAY = dict(noop_start=3, seed=101, sigma=0.0)        # the HOLDOUT display episode (as best.mp4 in 4b)
H_REF = 0.5
PANEL_W, PANEL_H, SCALE_MARIO = 360, 480, 2
POP_COLORS = {"LC4": (229, 135, 57), "LPLC2": (112, 158, 25), "DNp01": (38, 89, 217), "TTMn": (103, 103, 230),
              "DNp09": (210, 160, 60), "LC10a": (200, 120, 200), "DNa": (60, 200, 220)}   # BGR
GROUPS = {"LC4": ["LC4_L", "LC4_R"], "LPLC2": ["LPLC2_L", "LPLC2_R"], "DNp01": ["DNp01"], "TTMn": ["TTMn"],
          "DNp09": ["DNp09"], "LC10a": ["LC10a_L", "LC10a_R"], "DNa": ["DNa_L", "DNa_R"]}


class Panel:
    def __init__(self, brain):
        z = np.load(CLIPS / "soma_xyz.npz")
        cast, bg = z["cast"], z["bg"]
        s = (PANEL_H - 40) / 135000.0
        self.pos = lambda p: np.stack([20 + p[:, 0] * s, 30 + p[:, 2] * s], 1).astype(int)
        self.cast_px = self.pos(cast)
        self.base = np.full((PANEL_H, PANEL_W, 3), 20, np.uint8)
        for x, y in self.pos(bg):
            if 0 <= x < PANEL_W and 0 <= y < PANEL_H:
                self.base[y, x] = (70, 70, 70)
        self.pop = {}
        for name, ms in GROUPS.items():
            self.pop[name] = np.where(np.any([brain.masks[m] for m in ms], axis=0))[0]
        self.other = np.setdiff1d(np.arange(brain.K), np.concatenate(list(self.pop.values())))
        cv2.putText(self.base, "fly brain, soma x-z", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)
        for i, (n, c) in enumerate(POP_COLORS.items()):
            cv2.putText(self.base, n, (PANEL_W - 70, 18 + 15 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.4, c, 1, cv2.LINE_AA)

    def draw(self, h):
        img = self.base.copy()
        for i in self.other:
            x, y = self.cast_px[i]
            cv2.circle(img, (int(x), int(y)), 1, (95, 95, 95), -1)
        for name, idx in self.pop.items():
            col = np.array(POP_COLORS[name], float)
            for i in idx:
                a = float(min(1.0, h[i] / H_REF))
                x, y = self.cast_px[i]
                cv2.circle(img, (int(x), int(y)), int(round(2 + 4 * a)),
                           tuple(int(v) for v in (0.25 * col + 0.75 * a * col)), -1)
        return img


def put(img, text, org, scale=0.5, color=(255, 255, 255)):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1, cv2.LINE_AA)


def mario(rgb):
    return cv2.cvtColor(cv2.resize(np.ascontiguousarray(rgb), None, fx=SCALE_MARIO, fy=SCALE_MARIO,
                                   interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)


def readout(row):
    d = "-" if pd.isna(row.stim_d) else f"{float(row.stim_d):.0f}"
    return (f"frame {int(row.frame):4d}  x {int(row.x):4d}  stim {row.stim_src}  d {d} px  "
            f"theta {np.degrees(row.theta):5.1f} deg  TTMn {row.ttmn:5.2f}  A {'ON ' if row.a else 'off'}")


def run(knobs, brain, ctl=None, ep=DISPLAY):
    return run_episode(replace(knobs, SENSOR_NOISE=ep["sigma"]), brain, noop_start=ep["noop_start"],
                       episode_seed=ep["seed"], controller=CONTROLLERS[ctl] if ctl else None,
                       record=True, record_h=True, stuck_frames=150)


def write(path, frames, fps=30):
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(f)
    vw.release()


def fly_clip(path, df, panel, lo, hi, title, banner=None):
    frames_rgb, H = df.attrs["frames"], df.attrs["H"]
    out = []
    for i in range(lo, min(hi, len(df))):
        top = np.concatenate([mario(frames_rgb[i + 1]), panel.draw(H[i])], 1)
        bar = np.zeros((70, top.shape[1], 3), np.uint8)
        put(bar, readout(df.iloc[i]), (8, 24), 0.5)
        put(bar, title, (8, 52), 0.45, (180, 220, 255))
        fr = np.concatenate([top, bar], 0)
        if banner:
            cv2.rectangle(fr, (0, 0), (fr.shape[1], 34), (0, 0, 160), -1)
            put(fr, banner, (10, 24), 0.7)
        out.append(fr)
    write(path, out)
    return len(out)


def side_by_side(path, left, right):
    (dfl, tl), (dfr, tr) = left, right
    n = max(len(dfl), len(dfr))
    out = []
    for i in range(n):
        cols = []
        for df, t in ((dfl, tl), (dfr, tr)):
            j = min(i, len(df) - 1)
            m = mario(df.attrs["frames"][j + 1])
            bar = np.zeros((96, m.shape[1], 3), np.uint8)
            r = df.iloc[j]
            put(bar, t, (8, 20), 0.42, (180, 220, 255))
            put(bar, f"x {int(r.x):4d}  theta {np.degrees(r.theta):5.1f} deg  A {'ON ' if r.a else 'off'}", (8, 46), 0.5)
            put(bar, "(ended)" if i >= len(df) else f"frame {int(r.frame)}", (8, 72), 0.5)
            cols.append(np.concatenate([m, bar], 0))
        out.append(np.concatenate(cols, 1))
    write(path, out)
    return n


def main():
    CLIPS.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    os.environ.pop("FLYRUN_WFILE", None)
    brain = load_brain()
    panel = Panel(brain)
    g4 = decode("fly", np.array(json.loads((PART4 / "fly" / "best_genome.json").read_text())["u"]))[0]
    g4b = decode("fly", np.array(json.loads((EVO4 / "fly" / "best_genome.json").read_text())["u"]))[0]
    gth = decode("theta", np.array(json.loads((EVO4 / "theta" / "best_genome.json").read_text())["u"]))[0]
    N = {}

    # 01 + 02: default knobs, sigma 0, no delay
    d0 = dict(noop_start=0, seed=None, sigma=0.0)
    s, df = run(BASE, brain, ep=d0)
    df.to_csv(DATA / "default_knobs_log.csv", index=False)
    f1 = int(df.index[df.a == 1][0])
    land = int(df.index[(df.index > f1) & (df.air == 0)][0])
    n1 = fly_clip(CLIPS / "01_goomba_jump.mp4", df, panel, max(0, f1 - 75), land + 25,
                  "default knobs (G .5, TTMn>=.10, hold 12, cool 10), sigma 0, real wiring: Goomba #1")
    r1 = df.iloc[f1]
    N["01"] = [("first A at frame", f1), ("Mario x at first A", int(r1.x)), ("stim source", r1.stim_src),
               ("distance to threat at first A (px)", None if pd.isna(r1.stim_d) else float(r1.stim_d)),
               ("theta at first A (deg)", round(float(np.degrees(r1.theta)), 1)),
               ("TTMn at first A", round(float(r1.ttmn), 3)), ("clip frames", n1),
               ("episode end", f"{s['end_reason']} at x {s['x_at_end']} ({s['cause']})")]
    stuck_lo = int(df.index[df.x >= 560][0]) - 30
    n2 = fly_clip(CLIPS / "02_pipe3_stuck.mp4", df, panel, max(0, stuck_lo), len(df),
                  "default knobs, real wiring: the same run, pipe 3")
    N["02"] = [("max_x", s["max_x"]), ("end", f"{s['end_reason']} at x {s['x_at_end']}"), ("cause", s["cause"]),
               ("episode frames", s["frames"]), ("clip frames", n2)]

    # 03: theta rule vs fly, HOLDOUT display episode
    sf, dff = run(g4b, brain)
    st, dft = run(gth, brain, ctl="theta_rule")
    dff.to_csv(DATA / "fly4b_display_log.csv", index=False)
    dft.to_csv(DATA / "theta4b_display_log.csv", index=False)
    n3 = side_by_side(CLIPS / "03_theta_rule_vs_fly.mp4",
                      (dft, f"THETA RULE (no brain) theta*={gth.THETA_RULE_DEG:.1f} deg hold {gth.A_HOLD} cool {gth.COOLDOWN}"),
                      (dff, f"FLY CIRCUIT (4b) G {g4b.G:.2f} TTMN {g4b.TTMN_THRESH:.2f} hold {g4b.A_HOLD} cool {g4b.COOLDOWN}"))
    N["03"] = [("episode", "HOLDOUT noop_start 3, seed 101, sigma 0"),
               ("theta rule: max_x / end / blind presses", f"{st['max_x']} / {st['cause']} / {st['blind_presses']} of {st['n_onsets']}"),
               ("fly 4b: max_x / end / blind presses", f"{sf['max_x']} / {sf['cause']} / {sf['blind_presses']} of {sf['n_onsets']}"),
               ("theta* (deg)", round(gth.THETA_RULE_DEG, 2)), ("clip frames", n3)]

    # 04: the 4b fly montage (already labelled "gen N | max_x | cause")
    shutil.copy(EVO4 / "fly" / "montage.mp4", CLIPS / "04_evolution_montage.mp4")
    N["04"] = [("labels", "gen | max_x | death cause of that generation's best genome (HOLDOUT noop_start 3, sigma 0)"),
               ("stages", "runs/004_report_numbers.json, fly.montage_stages")]

    # 05: Part 4 hopper flag run
    s5, d5 = run(g4, brain)
    d5.to_csv(DATA / "hopper_display_log.csv", index=False)
    n5 = fly_clip(CLIPS / "05_flag_run.mp4", d5, panel, 0, len(d5),
                  "Part 4 genome, HOLDOUT noop_start 3, seed 101, sigma 0",
                  banner="EVOLVED  |  deterministic  |  fails under 5% noise")
    N["05"] = [("end", f"{s5['end_reason']} x {s5['x_at_end']}"), ("frames", s5["frames"]),
               ("A_frac", round(s5["a_frac"], 2)), ("blind presses", f"{s5['blind_presses']} of {s5['n_onsets']}"),
               ("'fails under 5% noise'", "flag 5 of 5 at sigma 0 but 0 of 5 at sigma 0.05 (HOLDOUT): runs/004_robust.md table 3, runs/005_controls.json holdout[real/part4_hopper]"),
               ("clip frames", n5)]

    # 06: the shuffled brain's best run = highest max_x over every Part 5 shuffle HOLDOUT episode
    ctl = json.loads((ROOT / "runs" / "005_controls.json").read_text())
    gs = {"default_knobs": BASE, "part4_hopper": g4, "part4b_fly": g4b}
    p = EVO5 / "fly_shuf" / "best_genome.json"
    if p.exists():
        gs["shuf_evolved"] = decode("fly", np.array(json.loads(p.read_text())["u"]))[0]
    best = None
    for name in gs:
        for i, mx in enumerate(ctl["holdout"][f"shuf/{name}"]["max_x"]):
            if best is None or mx > best[0]:
                best = (mx, name, i)
    _, name, i = best
    ep = HOLDOUT[i]
    sb = Brain(W=np.load(CACHE / "W_steer_shuf0.npy"), bodies=brain.bodies, masks=brain.masks)
    s6, d6 = run(gs[name], sb, ep=ep)
    d6.to_csv(DATA / "shuffle_best_log.csv", index=False)
    n6 = fly_clip(CLIPS / "06_shuffle.mp4", d6, Panel(sb), 0, len(d6),
                  f"SHUFFLED wiring, genome {name}, HOLDOUT nstart {ep['noop_start']} sigma {ep['sigma']} seed {ep['seed']}",
                  banner="CONTROL  |  degree-shuffled connectome")
    N["06"] = [("genome", name), ("episode", str(ep)), ("max_x", s6["max_x"]),
               ("end", f"{s6['end_reason']} ({s6['cause']})"),
               ("blind presses", f"{s6['blind_presses']} of {s6['n_onsets']}"), ("clip frames", n6)]

    src = {"01": "clips/data/default_knobs_log.csv", "02": "clips/data/default_knobs_log.csv",
           "03": "clips/data/fly4b_display_log.csv, clips/data/theta4b_display_log.csv",
           "04": "evo4/fly/montage.mp4 (copied), evo4/fly/gen.csv", "05": "clips/data/hopper_display_log.csv",
           "06": "clips/data/shuffle_best_log.csv, runs/005_controls.json"}
    lines = ["# clips/numbers.md", "",
             "Every number drawn on screen, with its source. Per-frame values (frame, x, stim source, d, theta, TTMn, A)",
             "are rows of the run's per-frame log in `clips/data/`; the clip is those rows rendered. Soma brightness = min(1, h/0.5).",
             "Headline numbers below are those quoted in titles/banners or used to choose the clip.", ""]
    for k, rows in N.items():
        lines += [f"## clip {k}  (source: {src[k]})", "", "| quantity | value |", "|---|---|"]
        lines += [f"| {q} | {v} |" for q, v in rows] + [""]
    (CLIPS / "numbers.md").write_text("\n".join(lines), encoding="utf-8")
    print("clips done")


if __name__ == "__main__":
    main()
