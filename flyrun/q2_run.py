"""Part Q2: hit the mushroom block (x 336) with the hum alone. One sense at a time: HUM_SENSE on, looming OFF (enemy, pipe, pit senses off), home signal on as usual.
Enemies removed (slots 0-4 zeroed after every step; the mushroom slot 5 is NOT touched). HUM_GAIN stays 14.5342 (frozen in Q1).
python -m flyrun.q2_run -> runs/Q2_window336.csv, runs/Q2_run.csv, runs/Q2_arms.json, clips/Q2_mushroom_block.mp4"""
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E
from . import level
from . import senses_v2 as SV
from .knobs import Knobs
from .o0_ram import Sim
from . import q1_run as Q1

ROOT = Path(__file__).resolve().parent
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0, PIPE_SENSE=False, PIT_SENSE=False)   # looming off; HUM_SENSE set per arm
BLOCKS = Q1.BLOCKS
SLOT = 5
TAIL_AFTER_EMERGE, TAIL_AFTER_EATEN, MAX_FRAMES = 200, 60, 700


def window336():
    """Scripted, no fly (as Q1): take-off offsets -40..+16 px from block 336's left edge, Right+A held until the bump. Which tile changed: 336, a brick (320 / 352), or 368?"""
    cols = (304, 320, 336, 352, 368, 384)
    rows = []
    for off in range(-40, 17):
        sim = Sim(remove=True)
        while sim.mx < 336 + off:
            sim.step(E.RIGHT)
        x0 = sim.mx
        before = {c: level.tile(sim.ram, c, 7) for c in cols}
        air, hit_cols = False, []
        for f in range(70):
            sim.step(E.RIGHT_A)
            air = air or int(sim.ram[0x001D]) != 0
            now = {c: level.tile(sim.ram, c, 7) for c in cols}
            hit_cols = [c for c in cols if now[c] != before[c]]
            if hit_cols:
                break
            if air and int(sim.ram[0x001D]) == 0:
                break
        rows.append(dict(takeoff_x=x0, offset_from_336=x0 - 336, hit_cols=hit_cols, hit_336=336 in hit_cols, mushroom_slot=bool(sim.ram[0x0F + SLOT]), frames=f + 1))
    return pd.DataFrame(rows).drop_duplicates("takeoff_x")


def run_arm(wfile, hum, record=False):
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, "steer_jo_bodies.parquet"
    from . import run as R
    from .brain import load_brain
    brain = load_brain()
    env = R._get_env()
    ram = env.unwrapped.ram
    orig = env.step
    trace = []
    state = dict(emerge=None, eaten=None, deadline=MAX_FRAMES)

    def step(action):
        out = orig(action)
        for s in range(5):
            ram[0x0F + s] = 0                                  # enemies removed; slot 5 (the power-up) untouched
        mx, feet = E.mario_x(ram), int(ram[0xCE])
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        f = len(trace)
        m_on = int(ram[0x0F + SLOT])
        sg = lambda v: v - 256 if v > 127 else v
        pw = int(ram[0x0756])
        trace.append(dict(screen_left=left, coins=int(ram[0x075E]), powerup=pw, mushroom=m_on,
                          mushroom_x=int(ram[0x6E + SLOT]) * 256 + int(ram[0x87 + SLOT]) if m_on else None, mushroom_y=int(ram[0xCF + SLOT]) if m_on else None,
                          mushroom_state=int(ram[0x1E + SLOT]) if m_on else None, mushroom_xspd=sg(int(ram[0x58 + SLOT])) if m_on else None,
                          n_hum=int(SV.hum_block(mx, feet, level.scan_blocks(ram)) is not None),
                          tiles={w: (level.tile(ram, w, 7) if left <= w < left + 240 else None) for w in BLOCKS}))
        if m_on and state["emerge"] is None:
            state["emerge"] = f
            state["deadline"] = f + TAIL_AFTER_EMERGE
        if state["emerge"] is not None and not m_on and state["eaten"] is None and f > state["emerge"] + 5:
            state["eaten"] = f
            state["deadline"] = min(state["deadline"], f + TAIL_AFTER_EATEN)
        if f >= state["deadline"]:
            return out[0], out[1], True, out[3]
        return out
    env.step = step
    try:
        s, df = R.run_episode(replace(KN, HUM_SENSE=hum), brain, noop_start=0, max_frames=MAX_FRAMES + 5, stuck_frames=10 ** 6, record=record, enemy_input=False)
    finally:
        del env.step
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    tr = pd.DataFrame(trace)
    for col in tr.columns.drop("tiles"):
        df[col] = tr[col].to_numpy()
    df["tiles"] = tr.tiles.to_numpy()
    df.attrs["emerge"], df.attrs["eaten"] = state["emerge"], state["eaten"]
    return s, df


def blocks(df):
    """Q1's per-block table, with coin / mushroom measured locally (the counters in the 8 frames after each block's own bump)."""
    rows = Q1.block_table(df)
    for r in rows:
        h = r["hit_frame"]
        if h is None:
            continue
        r["coin_out"] = int(df.coins.iloc[min(h + 8, len(df) - 1)]) - int(df.coins.iloc[max(h - 1, 0)])
        r["mushroom_out"] = bool(df.mushroom.iloc[max(h - 1, 0)] == 0 and df.mushroom.iloc[h:h + 4].any())   # a NEW mushroom appears with this bump
    return rows


def mushroom_report(df):
    m = df[df.mushroom == 1]
    if m.empty:
        return dict(out=False)
    path = [(int(r.frame), int(r.mushroom_x)) for r in m.itertuples() if (int(r.frame) - int(m.frame.iloc[0])) % 10 == 0]
    xs = m.mushroom_xspd.to_numpy()
    flips = [(int(m.frame.iloc[i]), int(m.mushroom_x.iloc[i])) for i in range(1, len(m)) if xs[i] != xs[i - 1] and xs[i] != 0 and xs[i - 1] != 0]
    eaten = df.attrs["eaten"]
    res = dict(out=True, emerge_frame=int(m.frame.iloc[0]), path_every_10=path, bounces=flips, last_seen_frame=int(m.frame.iloc[-1]),
               last_seen_x=int(m.mushroom_x.iloc[-1]), eaten=eaten is not None, eaten_frame=eaten, powerup_max=int(df.powerup.max()),
               mario_x_at_end=int(df.x.iloc[-1]), mario_x_at_eaten=int(df.x.iloc[min(eaten, len(df) - 1)]) if eaten is not None else None)
    if eaten is None:
        res["why_not_eaten"] = f"slot still active at the end (mushroom x {int(m.mushroom_x.iloc[-1])}, Mario x {int(df.x.iloc[-1])})" if df.mushroom.iloc[-1] else "slot inactive without a power-up (despawned)"
    return res


def main():
    res = {}
    w = window336()
    w.to_csv(ROOT / "runs" / "Q2_window336.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 220)
    print(w[["takeoff_x", "offset_from_336", "hit_cols", "hit_336", "mushroom_slot", "frames"]].to_string(index=False))
    h = w[w.hit_336]
    res["window336"] = dict(offsets=[int(x) for x in h.offset_from_336], lo=int(h.offset_from_336.min()) if len(h) else None, hi=int(h.offset_from_336.max()) if len(h) else None,
                            other_hits=[(int(r.offset_from_336), r.hit_cols) for r in w.itertuples() if r.hit_cols and not r.hit_336])
    print("336 window:", res["window336"]["lo"], "..", res["window336"]["hi"], "| hits elsewhere:", res["window336"]["other_hits"])
    s, df = run_arm("W_steer_jo.npy", True, record=True)
    out = Q1.csv_cols(df)
    for c in ("mushroom", "mushroom_x", "mushroom_y", "mushroom_state", "powerup", "coins"):
        out[c if c != "mushroom" else "mushroom_active"] = df[c].to_numpy()
    out.to_csv(ROOT / "runs" / "Q2_run.csv", index=False, lineterminator="\n")
    res["hum_on"] = dict(frames=s["frames"], max_x=s["max_x"], a_frames=int(df.a.sum()), left_presses=s.get("left_presses"), blocks=blocks(df), jumps=Q1.jumps(df).to_dict("records"),
                         mushroom=mushroom_report(df), a_no_block_no_threat=int(((df.a == 1) & (df.n_hum == 0)).sum()))
    print("HUM on:", {k: res["hum_on"][k] for k in ("frames", "max_x", "a_frames", "left_presses")})
    for b in res["hum_on"]["blocks"]:
        print("  ", b)
    print(Q1.jumps(df).to_string(index=False))
    print("mushroom:", res["hum_on"]["mushroom"])
    Q1.clip(df, ROOT / "clips" / "Q2_mushroom_block.mp4")
    for name, wfile, hum in [("hum_off", "W_steer_jo.npy", False)] + [(f"shuf{i}", f"W_steer_jo_shuf{i}_rn.npy", True) for i in range(5)]:
        s, d = run_arm(wfile, hum)
        res[name] = dict(frames=s["frames"], max_x=s["max_x"], a_frames=int(d.a.sum()), a_frames_no_block_in_view=int(((d.a == 1) & (d.n_hum == 0)).sum()), left_presses=s.get("left_presses"),
                         blocks=blocks(d), jumps=Q1.jumps(d).to_dict("records"), mushroom=mushroom_report(d))
        print(name, {k: res[name][k] for k in ("frames", "max_x", "a_frames", "a_frames_no_block_in_view", "left_presses")}, "hits", [b["hit"] for b in res[name]["blocks"]],
              "mushroom out/eaten", res[name]["mushroom"].get("out"), res[name]["mushroom"].get("eaten"))
    json.dump(res, open(ROOT / "runs" / "Q2_arms.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
