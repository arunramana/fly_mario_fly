"""Part M2b: smell-only (Scene A: the M2 setup with HOME off) and a mushroom moving AWAY (Scene B, the real test). 881-neuron brain, SMELL_GAIN / HUM_GAIN frozen.
Scene B method: the scripted driver (enemies removed) takes Mario over pit 1 / pit 2 to the flat stretch x 1424..2144 and hands over on the ground at x >= 1700; a mushroom is then
CREATED by RAM in the power-up slot (slot 5, type 0x2E, active flag, state 128, y 184 = on the ground) 64 px behind him (x - 64), moving LEFT (direction 2, speed -16 = 1 px/frame).
Nothing to his right stops him for 440 px (the next obstacle is the staircase at x 2144). Looming off, hum off.
python -m flyrun.m2b_run -> runs/M2b_*.csv, runs/M2b_arms.json, clips/M2b_away.mp4"""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import scripted
from .knobs import toggle_set
from .m2_run import BODIES, KN, csv_cols, run_fly, setup as setup_A
from .o0_ram import Sim

ROOT = Path(__file__).resolve().parent
WFILE = "W_steer_jo_orn.npy"
FRAMES = 400
BEHIND = 64
SLOT = 5


def setup_B(mushroom=True, behind=BEHIND):
    sim = Sim(remove=True)
    drv = scripted.Driver()
    for f in range(6000):
        if sim.mx >= 1700 and int(sim.ram[0x001D]) == 0:
            break
        sim.step(drv.act(sim.ram))
    r = sim.ram
    if mushroom:
        x = sim.mx - behind
        r[0x0F + SLOT], r[0x16 + SLOT], r[0x1E + SLOT] = 1, 0x2E, 128
        r[0x6E + SLOT], r[0x87 + SLOT], r[0xCF + SLOT] = x // 256, x % 256, 184
        r[0x46 + SLOT], r[0x58 + SLOT], r[0xA0 + SLOT] = 2, 0xF0, 0
    return sim, dict(mario_x=sim.mx, mario_feet=int(r[0xCE]), mushroom=sim.powerup(), free_ahead_to_x=2144)


def summarise(df, hand_x):
    left = df.left.to_numpy()
    runs, k = [], 0
    while k < len(left):
        if left[k]:
            j = k
            while j < len(left) and left[j]:
                j += 1
            runs.append((k, j - k))
            k = j
        else:
            k += 1
    sus = next((a for a, n in runs if n >= 5), None)
    smin = float(df.steer.min())
    e = df.attrs["eaten"]
    gone = e is not None
    ate = gone and int(df.powerup.max()) > 0
    r = dict(frames=len(df), left_frames=int(left.sum()), left_runs=runs, sustained_turn_frame=sus, turned_back=sus is not None,
             steer_min=smin, steer_max_margin_beyond_minus_0_01=-0.01 - smin, steer_crossed_frames=int((df.steer < -0.01).sum()),
             dnp09_mean=float(df.dnp09.mean()), dnp09_max=float(df.dnp09.max()), x_start=int(df.x.iloc[0]), x_min=int(df.x.min()), x_max=int(df.x.max()), x_end=int(df.x.iloc[-1]),
             left_distance=int(hand_x - df.x.min()), right_distance=int(df.x.max() - hand_x), a_frames=int(df.a.sum()),
             eaten=bool(ate), eaten_frame=e if ate else None, mario_x_at_eaten=int(df.x.iloc[e]) if ate else None, powerup_max=int(df.powerup.max()),
             mushroom_lost=bool(gone and not ate), lost_frame=e if (gone and not ate) else None)
    if sus is not None and not pd.isna(df.mushroom_x.iloc[sus]):
        r["gap_at_turn"] = int(df.x.iloc[sus] - df.mushroom_x.iloc[sus])
    return r


def one(tag, smell, home, setup_fn, hand_x_default, wfile=WFILE, sigma=0.0, seed=0, mushroom=True, frames=FRAMES, record=False, save_csv=False):
    s, df = run_fly(wfile, smell, sigma=sigma, seed=seed, mushroom=mushroom, record=record, frames=frames, home=home, setup_fn=setup_fn)
    hand = df.attrs["hand"]
    r = summarise(df, hand["mario_x"])
    r["toggles"] = toggle_set(replace(KN, SMELL_SENSE=smell, HOME_SENSE=home), enemy_input=False)
    r["hand"] = hand
    if save_csv:
        out = csv_cols(df)
        out["toggles"] = json.dumps(r["toggles"], separators=(",", ":"))
        out.to_csv(ROOT / "runs" / f"M2b_{tag}.csv", index=False, lineterminator="\n")
    return r, df


def clip(parts, path):
    import cv2
    S = 3
    fr0 = parts[0][0].attrs["frames"][0]
    h, w = fr0.shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 60, (w * S + 300, h * S))
    n = 0
    for df, label in parts:
        fr = df.attrs["frames"]
        for k in range(len(df)):
            r = df.iloc[k]
            img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(fr[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
            if isinstance(r.smell_box, tuple):
                bx, top, bw, bh = r.smell_box
                sx = bx - r.screen_left
                cv2.rectangle(img, (int(sx * S), int((top + 32) * S)), (int((sx + bw) * S), int((top + 32 + bh) * S)), (0, 220, 0), 3)
            pan = np.full((h * S, 300, 3), 24, np.uint8)

            def put(t, y, c=(255, 255, 255), sc=0.45):
                cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
            put("M2b: mushroom moving AWAY", 20, sc=0.42)
            put(label, 44, (0, 200, 255), 0.42)
            put(f"1x  frame {int(r.frame)}  Mario x {int(r.x)}", 68, sc=0.42)
            put(f"mushroom x {'-' if pd.isna(r.mushroom_x) else int(r.mushroom_x)}   power-up {int(r.powerup)}", 90, (0, 220, 0), 0.42)
            put(f"smell L {r.smell_L:5.1f}   R {r.smell_R:5.1f}", 118, (0, 220, 0))
            put(f"steer (DNa R-L) {r.steer:+.4f}   DNp09 {r.dnp09:.2f}", 146, sc=0.4)
            cv2.rectangle(pan, (8, 154), (288, 170), (70, 70, 70), 1)
            mid = 148
            cv2.line(pan, (mid, 150), (mid, 174), (255, 255, 255), 1)
            for t in (-0.01, 0.01):
                cv2.line(pan, (int(mid + t / 0.06 * 130), 150), (int(mid + t / 0.06 * 130), 174), (0, 140, 255), 2)
            cv2.circle(pan, (int(np.clip(mid + r.steer / 0.06 * 130, 10, 286)), 162), 5, (0, 255, 255), -1)
            put("orange ticks = +-0.01", 190, (0, 140, 255), 0.36)
            btn = "LEFT" if r.left else ("RIGHT" if r.right else "none")
            put(f"button: {btn}", 220, (0, 255, 0) if r.left else (200, 200, 200))
            put("orange = invented smell cue / gain", 700, (0, 140, 255), 0.38)
            put("teal = real ORN -> ... -> DNa", 720, (200, 200, 0), 0.38)
            vw.write(np.concatenate([img, pan], axis=1))
            n += 1
    vw.release()
    print("clip", path.name, n, "frames = %.1f s at 1x" % (n / 60))


def extra_near():
    """Not asked for, clearly labelled: the same Scene B with the mushroom only 32 px behind him (the screen never scrolls back, so at 64 px he runs out of screen)."""
    res = json.load(open(ROOT / "runs" / "M2b_arms.json"))
    near = lambda mushroom=True: setup_B(mushroom, behind=32)
    for tag, home in (("B1_near32", True), ("B2_near32", False)):
        r, _ = one(tag, True, home, near, 1700, save_csv=True)
        res[tag] = r
        print(tag, {k: v for k, v in r.items() if k not in ("toggles", "hand")})
    json.dump(res, open(ROOT / "runs" / "M2b_arms.json", "w"), indent=1, default=float)


def main():
    res = {}
    pd.set_option("display.width", 200)
    # ---- Scene A: the M2 setup, HOME off
    r, df = one("A_smell_on_home_off", True, False, setup_A, 560, save_csv=True)
    res["A"] = r
    print("A (smell on, home off):", {k: v for k, v in r.items() if k not in ("toggles", "hand")})
    r0, _ = one("A_smell_off_home_off", False, False, setup_A, 560, save_csv=True)
    res["A_both_off"] = r0
    print("A control (both off):", {k: v for k, v in r0.items() if k not in ("toggles", "hand")})
    # ---- Scene B: moving away, four arms
    parts = []
    for tag, smell, home in (("B1", True, True), ("B2", True, False), ("B3", False, True), ("B4", False, False)):
        r, df = one(tag, smell, home, setup_B, 1700, record=tag in ("B1", "B2"), save_csv=True)
        res[tag] = r
        nm, _ = one(tag + "_nomush", smell, home, setup_B, 1700, mushroom=False, frames=200)
        res[tag]["no_mushroom_left_frames"] = nm["left_frames"]
        res[tag]["no_mushroom_left_runs"] = nm["left_runs"]
        res[tag]["no_mushroom_x_end"] = nm["x_end"]
        print(tag, {k: v for k, v in r.items() if k not in ("toggles", "hand")})
        if tag in ("B1", "B2"):
            parts.append((df, f"{tag}: smell {'on' if smell else 'off'}, home {'on' if home else 'off'} (looming off, hum off)"))
    print("hand-over B:", res["B1"]["hand"])
    clip(parts, ROOT / "clips" / "M2b_away.mp4")
    # ---- controls: 5 shuffled brains on B2
    for i in range(5):
        w = f"W_steer_jo_orn_shuf{i}_rn.npy"
        r, _ = one(f"B2_shuf{i}", True, False, setup_B, 1700, wfile=w)
        nm, _ = one(f"B2_shuf{i}_nomush", True, False, setup_B, 1700, wfile=w, mushroom=False, frames=200)
        r["no_mushroom_left_frames"] = nm["left_frames"]
        res[f"B2_shuf{i}"] = r
        print(f"B2 shuf{i}", {k: r[k] for k in ("turned_back", "left_frames", "eaten", "eaten_frame", "mushroom_lost", "x_min", "x_max", "no_mushroom_left_frames")})
    # ---- noise: B1 and B2, sigma 0.05, seeds 1-5
    for tag, home in (("B1", True), ("B2", False)):
        rows = []
        for seed in range(1, 6):
            r, _ = one(f"{tag}_n{seed}", True, home, setup_B, 1700, sigma=0.05, seed=seed)
            rows.append(dict(seed=seed, **{k: r[k] for k in ("turned_back", "left_frames", "eaten", "eaten_frame", "mario_x_at_eaten", "mushroom_lost", "x_min", "x_max", "steer_min")}))
            print(tag, "sigma 0.05 seed", seed, rows[-1])
        res[f"{tag}_noise"] = rows
    json.dump(res, open(ROOT / "runs" / "M2b_arms.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    import sys
    extra_near() if sys.argv[1:] == ["near"] else main()
