"""Part Q1 section 4-5: the "?" scene. Enemies removed (the O0 method: zero the active flags of enemy slots 0-4 after every step), the fly from the start to x 420.
Arms: the JO brain with HUM_SENSE on (the real fly), HUM_SENSE off (control), and the 5 shuffled JO brains with HUM_SENSE on.
python -m flyrun.q1_run -> runs/Q1_run.csv (HUM on), runs/Q1_arms.json, clips/Q1_hum.mp4"""
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

ROOT = Path(__file__).resolve().parent
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0)
MAX_X = 420
BLOCKS = {256: "coin (192)", 336: "mushroom (193)", 368: "coin (192)"}     # the reachable ? blocks before x 420 (352 row 3 is not reachable)
ADDR_COINS, ADDR_POWER = 0x075E, 0x0756


def run_arm(wfile, hum, record=False):
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, "steer_jo_bodies.parquet"
    from . import run as R
    from .brain import load_brain
    brain = load_brain()
    env = R._get_env()
    ram = env.unwrapped.ram
    orig = env.step
    trace = []

    def step(action):
        out = orig(action)
        for s in range(5):
            ram[0x0F + s] = 0                                  # enemies removed (slots 0-4; the power-up lives in slot 5)
        mx, feet = E.mario_x(ram), int(ram[0xCE])
        left = int(ram[0x071A]) * 256 + int(ram[0x071C])
        trace.append(dict(screen_left=left, coins=int(ram[ADDR_COINS]), powerup=int(ram[ADDR_POWER]), mushroom=int(ram[0x0F + 5]),
                          n_hum=int(SV.hum_block(mx, feet, level.scan_blocks(ram)) is not None),
                          tiles={w: (level.tile(ram, w, 7) if left <= w < left + 240 else None) for w in BLOCKS}))
        if mx >= MAX_X:
            return out[0], out[1], True, out[3]
        return out
    env.step = step
    try:
        s, df = R.run_episode(replace(KN, HUM_SENSE=hum), brain, noop_start=0, max_frames=1500, stuck_frames=10 ** 6, record=record)
    finally:
        del env.step
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    tr = pd.DataFrame(trace)
    for col in tr.columns.drop("tiles"):
        df[col] = tr[col].to_numpy()
    df["tiles"] = tr.tiles.to_numpy()
    return s, df


def jumps(df):
    """One row per grounded A onset: take-off position (his x BEFORE the press), the block heard, frames held."""
    rows = []
    a, air = df.a.to_numpy(), df.air.to_numpy()
    for k in range(len(df)):
        if a[k] == 1 and (k == 0 or a[k - 1] == 0) and (k == 0 or air[k - 1] == 0):
            held = int(np.argmax(a[k:] == 0)) if (a[k:] == 0).any() else len(a) - k
            hb = df.hum_block.iloc[k] if "hum_block" in df else None
            rows.append(dict(frame=k, takeoff_x=int(df.x.iloc[k - 1]) if k else 40, block=int(hb[0]) if isinstance(hb, tuple) else None, threat=df.threat_kind.iloc[k],
                             frames_held=held))
    return pd.DataFrame(rows)


def block_table(df):
    jt = jumps(df)
    out = []
    for bx, what in BLOCKS.items():
        t0 = None
        hit_frame = next((i for i, t in enumerate(df.tiles) if t[bx] in (35, 196)), None)
        heard = bool("hum_block" in df and any(isinstance(h, tuple) and h[0] == bx for h in df.hum_block))
        js = jt[jt.block == bx] if "block" in jt and len(jt) else jt
        if hit_frame is not None and len(js):
            js = js[js.frame <= hit_frame]
        coin0 = int(df.coins.iloc[max(hit_frame - 5, 0)]) if hit_frame is not None else None
        out.append(dict(block_x=bx, contents_by_id=what, heard=heard, takeoffs=[int(x) - bx for x in js.takeoff_x] if len(js) else [], frames_held=[int(h) for h in js.frames_held] if len(js) else [],
                        jumps_needed=len(js), hit=hit_frame is not None, hit_frame=hit_frame,
                        coin_out=(int(df.coins.iloc[min(hit_frame + 30, len(df) - 1)]) - coin0) if hit_frame is not None else None,
                        mushroom_out=bool(df.mushroom.iloc[hit_frame:].any()) if hit_frame is not None else False))
    return out


def clip(df, path):
    import cv2
    S = 3
    frames = df.attrs["frames"]
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 60, (w * S + 260, h * S))
    thr = KN.TTMN_THRESH
    for k in range(len(df)):
        r = df.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(frames[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        if isinstance(r.hum_block, tuple):
            bx, bottom, d = r.hum_block
            sx = bx - r.screen_left
            y = int((bottom + 32) * S)
            cv2.line(img, (int(sx * S), y + 2), (int((sx + 16) * S), y + 2), (0, 220, 0), 4)          # the GREEN line under the humming block
        pan = np.full((h * S, 260, 3), 24, np.uint8)

        def put(t, y, c=(255, 255, 255), sc=0.45):
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
        put("Q1: ? block hums -> JO -> GF", 20, sc=0.42)
        put(f"1x  frame {int(r.frame)}  x {int(r.x)}", 44, sc=0.42)
        hb = r.hum_block
        put(f"humming block: {int(hb[0]) if isinstance(hb, tuple) else '-'}", 70, (0, 220, 0) if isinstance(hb, tuple) else (200, 200, 200))
        put(f"hum level {r.hum_level:.2f}  (JO input)", 94, (0, 220, 0))
        put(f"TTMn {r.ttmn:.3f}  (thr {thr:.2f})", 126, (0, 255, 255) if r.ttmn >= thr else (255, 255, 255))
        cv2.rectangle(pan, (8, 134), (248, 148), (70, 70, 70), 1)
        cv2.rectangle(pan, (8, 134), (8 + int(min(1.0, r.ttmn / 0.2) * 240), 148), (0, 200, 255), -1)
        cv2.line(pan, (8 + int(thr / 0.2 * 240), 130), (8 + int(thr / 0.2 * 240), 152), (255, 255, 255), 1)
        put(f"A {'DOWN' if r.a else 'up'}", 184, (0, 255, 0) if r.a else (200, 200, 200))
        put(f"airborne {'YES' if r.air else 'no'}", 208, (0, 200, 255) if r.air else (200, 200, 200))
        put("orange = invented hum cue / gain", 700, (0, 140, 255), 0.38)
        put("teal = real JO -> GF -> TTMn", 720, (200, 200, 0), 0.38)
        vw.write(np.concatenate([img, pan], axis=1))
    vw.release()
    print("clip", path.name, len(df), "frames = %.1f s at 1x" % (len(df) / 60))


def csv_cols(df):
    out = df[["frame", "x", "y", "air", "threat_kind", "box", "theta", "ttmn", "a", "right", "left", "hum_block", "hum_level", "jo_input"]].copy()
    out["threat_box_x_top_w_h"] = out.box.map(lambda b: "" if not isinstance(b, tuple) else " ".join(str(int(v)) for v in b))
    out["hum_block"] = out.hum_block.map(lambda b: "" if not isinstance(b, tuple) else " ".join(f"{v:.1f}" if i == 2 else str(int(v)) for i, v in enumerate(b)))
    out["theta_deg"] = np.degrees(out.theta).round(2)
    out["ttmn"] = out.ttmn.round(4)
    out = out.rename(columns={"y": "feet_y", "air": "airborne", "threat_kind": "threat"}).drop(columns=["box", "theta"])
    return out[["frame", "x", "feet_y", "airborne", "threat", "threat_box_x_top_w_h", "theta_deg", "ttmn", "a", "right", "left", "hum_block", "hum_level", "jo_input"]]


def main():
    res = {}
    s, df = run_arm("W_steer_jo.npy", True, record=True)
    csv_cols(df).to_csv(ROOT / "runs" / "Q1_run.csv", index=False, lineterminator="\n")
    res["hum_on"] = dict(max_x=s["max_x"], frames=s["frames"], end=s["end_reason"], a_frac=s["a_frac"], left_presses=s.get("left_presses"), blocks=block_table(df),
                         jumps=jumps(df).to_dict("records"), powerup_max=int(df.powerup.max()), coins=int(df.coins.max()), a_frames=int(df.a.sum()),
                         a_frames_no_block_in_view=int(((df.a == 1) & (df.n_hum == 0)).sum()), a_frames_no_block_no_threat=int(((df.a == 1) & (df.n_hum == 0) & (df.threat_kind == "none")).sum()))
    print("HUM on:", {k: res["hum_on"][k] for k in ("max_x", "frames", "a_frac", "left_presses", "powerup_max", "coins")})
    for b in res["hum_on"]["blocks"]:
        print("  ", b)
    print(jumps(df).to_string(index=False))
    clip(df, ROOT / "clips" / "Q1_hum.mp4")
    for name, wfile, hum in [("hum_off", "W_steer_jo.npy", False)] + [(f"shuf{i}", f"W_steer_jo_shuf{i}_rn.npy", True) for i in range(5)]:
        s, d = run_arm(wfile, hum)
        a_no_block = int(((d.a == 1) & (d.n_hum == 0)).sum())
        a_nothing = int(((d.a == 1) & (d.n_hum == 0) & (d.threat_kind == "none")).sum())
        res[name] = dict(max_x=s["max_x"], frames=s["frames"], end=s["end_reason"], a_frac=s["a_frac"], left_presses=s.get("left_presses"), blocks=block_table(d), a_frames=int(d.a.sum()),
                         a_frames_no_block_in_view=a_no_block, a_frames_no_block_no_threat=a_nothing, jumps=jumps(d).to_dict("records"), powerup_max=int(d.powerup.max()))
        print(name, {k: res[name][k] for k in ("max_x", "frames", "a_frames", "a_frames_no_block_in_view", "a_frames_no_block_no_threat", "left_presses")}, "hits:", [b["hit"] for b in res[name]["blocks"]],
              "jumps:", [(j["takeoff_x"], j["block"], j["threat"]) for j in res[name]["jumps"]])
    d_on = res["hum_on"]
    json.dump(res, open(ROOT / "runs" / "Q1_arms.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
