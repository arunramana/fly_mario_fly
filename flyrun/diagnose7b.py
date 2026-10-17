"""Part 7b: replay evo6/real r3 on HOLDOUT with the full per-frame state needed to diagnose a death.
run.py / motor.py / senses.py are NOT changed: the replay wraps motor.decide (to read the Muscle's hold / cooldown after
each decision) and env.step (to snapshot RAM: Mario y, enemy slots) and checks it reproduces run_episode's own summary.
python -m flyrun.part7 --config flyrun/configs/part7.yaml --stage replay   (dumps all HOLDOUT episodes to runs/008b_replay/)
python -m flyrun.diagnose7b                                                  (tables + classification + clips; 7b step 2)"""
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "runs" / "008b_replay"
ADDR_MARIO_Y, ADDR_ENEMY_Y = 0x00CE, 0x00CF   # player screen y; enemy y per slot


def capture(knobs, ep, brain, record=False):
    """-> (summary, df). df = run_episode's telemetry + y, a_left, cool_left, enemies (text), enemy_n."""
    from . import motor, run as R
    env = R._get_env()
    snaps, mus = [], []
    orig_step, orig_decide = env.step, motor.decide
    cur = {}

    def decide(h, masks, kn, m):
        out = orig_decide(h, masks, kn, m)
        cur["a_left"], cur["cool_left"] = m.a_left, m.cool_left   # state AFTER this frame's decision
        return out

    def step(action):
        ram = env.unwrapped.ram
        mx = E.mario_x(ram)
        en = []
        for sl in range(E.N_ENEMY_SLOTS):
            if int(ram[E.ADDR_ENEMY_ACTIVE + sl]) and int(ram[E.ADDR_ENEMY_TYPE + sl]) != E.POWERUP_ID:
                dx = int(ram[E.ADDR_ENEMY_PAGE + sl]) * 256 + int(ram[E.ADDR_ENEMY_X + sl]) - mx
                if abs(dx) <= 100:
                    en.append(f"s{sl}:dx{dx:+d},y{int(ram[ADDR_ENEMY_Y + sl])},t{int(ram[E.ADDR_ENEMY_TYPE + sl]):02X}")
        snaps.append((int(ram[ADDR_MARIO_Y]), " ".join(en), len(en)))
        mus.append((cur.get("a_left", 0), cur.get("cool_left", 0)))
        cur.clear()
        return orig_step(action)

    env.step, motor.decide = step, decide
    try:
        s, df = R.run_episode(knobs, brain, noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150,
                              record=record)
    finally:
        del env.step                      # drop the instance attribute: back to the class method
        motor.decide = orig_decide
    assert len(snaps) == len(df)
    df["y"] = [a for a, _, _ in snaps]
    df["enemies"] = [b for _, b, _ in snaps]
    df["enemy_n"] = [c for _, _, c in snaps]
    df["a_left"] = [a for a, _ in mus]
    df["cool_left"] = [c for _, c in mus]
    return s, df


def r3_knobs(cfg):
    from .part7 import decode
    return decode(cfg, next(r for r in cfg["restarts"] if r["label"] == "warm_r3")["u"])[0]


def dump_holdout(cfg, st):
    """Replay r3 on every HOLDOUT episode, write per-frame csvs (stamped) and a summary; check against run_episode."""
    from dataclasses import replace
    from .brain import load_brain
    from .part7 import LF, stamp_line
    brain, kn = load_brain(), r3_knobs(cfg)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, ep in enumerate(cfg["episodes"]["holdout"]):
        s, df = capture(replace(kn, SENSOR_NOISE=float(ep["sigma"])), ep, brain)
        with open(OUT / f"ep{i}.csv", "w", encoding="utf-8", newline=LF) as f:
            f.write(f"# warm_r3 HOLDOUT ep{i} {ep}  [{stamp_line(st)}]\n")
            df.to_csv(f, index=False, lineterminator=LF)
        rows.append(dict(ep=i, **ep, max_x=s["max_x"], flag=s["flag_get"], end=s["end_reason"], cause=s["cause"], frames=s["frames"]))
        print(rows[-1], flush=True)
    return rows


def load_ep(i):
    return pd.read_csv(OUT / f"ep{i}.csv", comment="#", keep_default_na=False, na_values=[""])


# ---------------------------------------------------------------- 7b step 2: tables + clips
DEATH_EP, FLAG_EP = 0, 5          # HOLDOUT indices: representative x~1219 death (noop 3, seed 101, sigma 0) and the flag run
X_CLIP = 1220                     # clips are +-3 s of game time around the first frame at x >= 1218


def table_md(d, f0, f1):
    """Markdown frame table for frames f0..f1 (the key columns of the diagnosis)."""
    rows = ["| frame | x | y | air | src | stim_d | theta | dtheta | ttmn | a | a_left | cool_left | enemies (dx,y,type) |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in d[(d.frame >= f0) & (d.frame <= f1)].itertuples():
        sd = "-" if pd.isna(r.stim_d) else f"{r.stim_d:.0f}"
        en = "" if pd.isna(r.enemies) else r.enemies
        rows.append(f"| {r.frame} | {r.x} | {r.y} | {r.air} | {r.stim_src} | {sd} | {np.degrees(r.theta):.1f} | "
                    f"{np.degrees(r.dtheta):.2f} | {r.ttmn:.3f} | {r.a} | {r.a_left} | {r.cool_left} | {en} |")
    return "\n".join(rows)


def first_a_frame(d, xmin=1150):
    on = d[(d.a == 1) & (d.a.shift(1, fill_value=0) == 0) & (d.x > xmin) & (d.stim_src == "goomba")]
    return int(on.iloc[0].frame)


def window_csvs(cfg, st):
    """Full dumps: death frames T-90..T, and the flag run over the same x window (x in [x(T-90), 1260], after the pit)."""
    from .part7 import LF, stamp_line
    dd, df_ = load_ep(DEATH_EP), load_ep(FLAG_EP)
    T = int(dd.frame.iloc[-1])
    w_death = dd[dd.frame >= T - 90]
    x_lo = int(w_death.x.iloc[0])
    w_flag = df_[(df_.frame > 640) & (df_.x >= x_lo) & (df_.x <= 1260)]
    for name, w in (("death_ep0_last90", w_death), ("flag_ep5_same_x_window", w_flag)):
        with open(OUT.parent / f"008b_{name}.csv", "w", encoding="utf-8", newline=LF) as f:
            f.write(f"# {name}  [{stamp_line(st)}]\n")
            w.to_csv(f, index=False, lineterminator=LF)
    return w_death, w_flag


def clip(cfg, ep_i, path, title):
    """+-3 s around the first frame at x >= 1218, played at 30 fps (= 0.5x of the NES's 60 Hz), with a stim_d / TTMn / hold overlay."""
    import cv2
    from dataclasses import replace
    from .brain import load_brain
    from .part7 import decode
    ep = cfg["episodes"]["holdout"][ep_i]
    kn = replace(r3_knobs(cfg), SENSOR_NOISE=float(ep["sigma"]))
    thr = kn.TTMN_THRESH
    s, d = capture(kn, ep, load_brain(), record=True)
    frames = d.attrs["frames"]                       # frames[k+1] = screen after row k's action
    f0 = int(d[d.x >= 1218].frame.iloc[0])
    lo, hi = max(0, f0 - 180), min(len(d) - 1, f0 + 180)
    S = 3
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (w * S + 260, h * S))
    for k in range(lo, hi + 1):
        r = d.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(frames[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        pan = np.full((h * S, 260, 3), 24, np.uint8)
        put = lambda t, y, c=(255, 255, 255), sc=0.5: (cv2.putText(pan, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA),
                                                        cv2.putText(pan, t, (10, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA))
        put(title, 22, sc=0.42)
        put(f"frame {int(r.frame)}   x {int(r.x)}  y {int(r.y)}", 48)
        sd = "-" if pd.isna(r.stim_d) else f"{r.stim_d:.0f} px"
        put(f"stim_d  {sd}   ({r.stim_src})", 74)
        put(f"theta {np.degrees(r.theta):5.1f} deg", 100)
        put(f"TTMn {r.ttmn:.3f}  (thr {thr:.3f})", 126, (0, 255, 255) if r.ttmn >= thr else (255, 255, 255))
        bar = int(min(1.0, r.ttmn / 1.0) * 240)
        cv2.rectangle(pan, (10, 134), (250, 148), (70, 70, 70), 1)
        cv2.rectangle(pan, (10, 134), (10 + bar, 148), (0, 200, 255), -1)
        cv2.line(pan, (10 + int(min(1.0, thr) * 240),) * 1 + (130,), (10 + int(min(1.0, thr) * 240), 152), (255, 255, 255), 1)
        put(f"A {'DOWN' if r.a else 'up'}   hold left {int(r.a_left)}", 182, (0, 255, 0) if r.a else (200, 200, 200))
        put(f"cooldown left {int(r.cool_left)}", 208, (0, 120, 255) if r.cool_left else (200, 200, 200))
        put(f"enemies: {'' if pd.isna(r.enemies) else r.enemies}", 240, sc=0.36)
        if k == len(d) - 1:
            put("END: " + s["cause"], 290, (0, 0, 255), 0.6)
        vw.write(np.concatenate([img, pan], axis=1))
    vw.release()
    return dict(ep=ep_i, f0=f0, frames=(lo, hi), n=hi - lo + 1, end=s["cause"])


def main():
    from .part7 import load_config, stamp
    cfg = load_config(ROOT / "configs" / "part7.yaml")
    st = stamp(ROOT / "configs" / "part7.yaml", cfg)
    wd, wf = window_csvs(cfg, st)
    dd, df_ = load_ep(DEATH_EP), load_ep(FLAG_EP)
    T = int(dd.frame.iloc[-1])
    fa_d, fa_f = first_a_frame(dd), first_a_frame(df_)
    (OUT.parent / "008b_tables.md").write_text(
        f"### Death (HOLDOUT ep{DEATH_EP}), frames {T - 39}..{T}\n\n{table_md(dd, T - 39, T)}\n\n"
        f"### Flag run (HOLDOUT ep{FLAG_EP}), same position in the jump (first-A aligned), frames {fa_f - (fa_d - (T - 39))}..{fa_f + (T - fa_d)}\n\n"
        f"{table_md(df_, fa_f - (fa_d - (T - 39)), fa_f + (T - fa_d))}\n", encoding="utf-8", newline=chr(10))
    clips = ROOT / "clips"
    print(clip(cfg, DEATH_EP, clips / "08b_death_1219.mp4", "r3 HOLDOUT ep0: death at x 1219"))
    print(clip(cfg, FLAG_EP, clips / "08b_flag_same_spot.mp4", "r3 HOLDOUT ep5: flag run, same spot"))


if __name__ == "__main__":
    main()
