"""Part M2: the mushroom BEHIND Mario: sweet smell (left antenna) vs the home signal (right).
Scene (O0 M2 setup): scripted hit of block 336 and a scripted run to x >= 560 (enemies removed), then the mushroom is placed 64 px behind Mario, on the ground, moving right at
1 px/frame, and the fly takes over from a silent brain. Senses: SMELL on, HOME on, looming OFF, hum OFF. 400 frames or until eaten.
python -m flyrun.m2_run -> checks, SMELL_GAIN calculation, runs/M2_run.csv, runs/M2_arms.json, clips/M2_smell.mp4"""
import json
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E
from . import level
from . import scripted
from .knobs import Knobs
from .o0_ram import Sim, hit_from_below

ROOT = Path(__file__).resolve().parent
BODIES = "steer_jo_orn_bodies.parquet"
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0, PIPE_SENSE=False, PIT_SENSE=False, HUM_SENSE=False)
SLOT, BEHIND, MAX_FRAMES, TAIL = 5, 64, 400, 20


def setup(mushroom=True):
    """Scripted prefix -> (sim, handover info). Leaves the emulator at the hand-over state (the caller backs it up)."""
    sim = Sim(remove=True)
    hit_from_below(sim, 336)
    drv = scripted.Driver()
    for f in range(1200):
        if sim.mx >= 560 and int(sim.ram[0x001D]) == 0 and sim.powerup():
            break
        sim.step(drv.act(sim.ram))
    r = sim.ram
    if mushroom:
        x = sim.mx - BEHIND
        r[0x6E + SLOT], r[0x87 + SLOT], r[0xCF + SLOT], r[0x46 + SLOT], r[0x58 + SLOT] = x // 256, x % 256, 184, 1, 16
    else:
        r[0x0F + SLOT] = 0
    return sim, dict(mario_x=sim.mx, mario_feet=int(r[0xCE]), mushroom=sim.powerup())


def run_fly(wfile, smell, sigma=0.0, seed=0, mushroom=True, record=False, frames=MAX_FRAMES, gain=None, home=True, setup_fn=None):
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, BODIES
    from . import run as R
    from .brain import load_brain
    sim, hand = (setup_fn or setup)(mushroom)
    brain = load_brain()
    env = R._get_env()
    ram = env.unwrapped.ram
    orig_step = env.step
    env.reset = lambda *a, **k: np.asarray(env.unwrapped.screen).copy()          # run_episode starts from the CURRENT (hand-over) state; nothing is backed up
    trace, st = [], dict(eaten=None)

    def step(action):
        out = orig_step(action)
        for s in range(5):
            ram[0x0F + s] = 0                                      # enemies removed (slot 5, the mushroom, untouched)
        m_on = int(ram[0x0F + SLOT])
        f = len(trace)
        trace.append(dict(screen_left=int(ram[0x071A]) * 256 + int(ram[0x071C]), powerup=int(ram[0x0756]), mushroom_active=m_on,
                          mushroom_x=int(ram[0x6E + SLOT]) * 256 + int(ram[0x87 + SLOT]) if m_on else None,
                          mushroom_xspd=(lambda v: v - 256 if v > 127 else v)(int(ram[0x58 + SLOT])) if m_on else None))
        if not m_on and mushroom and st["eaten"] is None and f > 0:
            st["eaten"] = f
        if st["eaten"] is not None and f >= st["eaten"] + TAIL:
            return out[0], out[1], True, out[3]
        return out
    env.step = step
    kn = replace(KN, SMELL_SENSE=smell, HOME_SENSE=home, SENSOR_NOISE=sigma, **({"SMELL_GAIN": gain} if gain is not None else {}))
    try:
        s, df = R.run_episode(kn, brain, noop_start=0, max_frames=frames, stuck_frames=10 ** 6, record=record, enemy_input=False, episode_seed=seed if sigma > 0 else None)
    finally:
        del env.step
        del env.reset
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    tr = pd.DataFrame(trace)
    for c in tr.columns:
        df[c] = tr[c].to_numpy()
    df.attrs["eaten"], df.attrs["hand"] = st["eaten"], hand
    return s, df


def summarise(df):
    left = df.left.to_numpy()
    onsets = [k for k in range(len(df)) if left[k] and (k == 0 or not left[k - 1])]
    first = onsets[0] if onsets else None
    r = dict(frames=len(df), left_frames=int(left.sum()), left_presses=len(onsets), x_min=int(df.x.min()), x_end=int(df.x.iloc[-1]), turned_back=bool(left.any()))
    if first is not None:
        r.update(first_left_frame=int(first), mario_x_at_turn=int(df.x.iloc[first]), mushroom_x_at_turn=None if pd.isna(df.mushroom_x.iloc[first]) else int(df.mushroom_x.iloc[first]),
                 gap_at_turn=None if pd.isna(df.mushroom_x.iloc[first]) else int(df.x.iloc[first] - df.mushroom_x.iloc[first]))
    runs, k = [], 0
    while k < len(left):                                      # Left runs: (start frame, length)
        if left[k]:
            j = k
            while j < len(left) and left[j]:
                j += 1
            runs.append((k, j - k))
            k = j
        else:
            k += 1
    r["left_runs"] = runs
    sus = next((a for a, n in runs if n >= 5), None)         # the first SUSTAINED turn (>= 5 frames); shorter runs are start-up transients of the brain
    r["sustained_turn_frame"] = sus
    if sus is not None and not pd.isna(df.mushroom_x.iloc[sus]):
        r["gap_at_sustained_turn"] = int(df.x.iloc[sus] - df.mushroom_x.iloc[sus])
        r["mario_x_at_sustained_turn"] = int(df.x.iloc[sus])
    e = df.attrs["eaten"]
    r.update(eaten=e is not None and int(df.powerup.max()) > 0, eaten_frame=e, mario_x_at_eaten=int(df.x.iloc[e]) if e is not None else None, powerup_max=int(df.powerup.max()),
             mushroom_x_end=None if pd.isna(df.mushroom_x.iloc[-1]) else int(df.mushroom_x.iloc[-1]))
    return r


def csv_cols(df):
    out = pd.DataFrame(dict(frame=df.frame, mario_x=df.x, mushroom_x=df.mushroom_x, gap=df.x - df.mushroom_x, smell_L=df.get("smell_L", 0.0), smell_R=df.get("smell_R", 0.0), steer_RminusL=df.steer, dnp09=df.dnp09,
                            left=df.left, right=df.right, a=df.a, powerup=df.powerup, mushroom_active=df.mushroom_active))
    out["dna_L_minus_R"] = -out.steer_RminusL
    return out.round(5)


def clip(df, path):
    import cv2
    S = 3
    fr = df.attrs["frames"]
    h, w = fr[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 60, (w * S + 280, h * S))
    for k in range(len(df)):
        r = df.iloc[k]
        img = cv2.cvtColor(cv2.resize(np.ascontiguousarray(fr[k + 1]), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        if isinstance(r.smell_box, tuple):
            bx, top, bw, bh = r.smell_box
            sx = bx - r.screen_left
            cv2.rectangle(img, (int(sx * S), int((top + 32) * S)), (int((sx + bw) * S), int((top + 32 + bh) * S)), (0, 220, 0), 3)    # GREEN box over the mushroom
        pan = np.full((h * S, 280, 3), 24, np.uint8)

        def put(t, y, c=(255, 255, 255), sc=0.45):
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(pan, t, (8, y), cv2.FONT_HERSHEY_SIMPLEX, sc, c, 1, cv2.LINE_AA)
        put("M2: mushroom behind: smell vs home", 20, sc=0.42)
        put(f"1x  frame {int(r.frame)}  Mario x {int(r.x)}", 44, sc=0.42)
        put(f"mushroom x {'-' if pd.isna(r.mushroom_x) else int(r.mushroom_x)}   power-up {int(r.powerup)}", 66, (0, 220, 0), 0.42)
        put(f"smell L {r.smell_L:5.1f}   R {r.smell_R:5.1f}", 96, (0, 220, 0))
        put(f"steer (DNa R-L) {r.steer:+.4f}", 126)
        cv2.rectangle(pan, (8, 134), (268, 150), (70, 70, 70), 1)
        mid = 138
        cv2.line(pan, (mid, 130), (mid, 154), (255, 255, 255), 1)
        for t in (-0.01, 0.01):
            cv2.line(pan, (int(mid + t / 0.06 * 130), 130), (int(mid + t / 0.06 * 130), 154), (0, 140, 255), 2)
        cv2.circle(pan, (int(np.clip(mid + r.steer / 0.06 * 130, 10, 266)), 142), 5, (0, 255, 255), -1)
        put("orange ticks = +-0.01 (the Left / Right threshold)", 170, (0, 140, 255), 0.36)
        btn = "LEFT" if r.left else ("RIGHT" if r.right else "none")
        put(f"button: {btn}", 200, (0, 255, 0) if r.left else (200, 200, 200))
        put("orange = invented smell cue / gain", 700, (0, 140, 255), 0.38)
        put("teal = real ORN -> ... -> DNa", 720, (200, 200, 0), 0.38)
        vw.write(np.concatenate([img, pan], axis=1))
    vw.release()
    print("clip", path.name, len(df), "frames = %.1f s at 1x" % (len(df) / 60))


# ------------------------------------------------------------------ section 1/2: checks and the gain
def drive_levels(wfile):
    """Left (and right) antenna attractive ORNs driven at a constant level, 100 frames; steer = DNa_R - DNa_L (negative = Left); with and without HOME_R."""
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = wfile, BODIES
    from .brain import load_brain, step
    brain = load_brain()
    del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    m = brain.masks
    rows = []

    def steady(I):
        h = np.zeros(brain.K)
        for _ in range(100 * KN.SUBSTEPS):
            h = step(h, brain.W, KN.G, I, KN.ALPHA, KN.CLIP)
        return float(h[m["DNa_R"]].mean() - h[m["DNa_L"]].mean()), float(h[m["DNa_L"]].mean()), float(h[m["DNa_R"]].mean()), float(h[m["DNp09"]].mean())
    for ant in "LR":
        for lvl in (0, 1, 2, 5, 10, 20, 30, 40, 45, 49, 50, 55, 60):
            for home in (False, True):
                I = np.zeros(brain.K)
                I[m["LC10a_R"]] = KN.HOME_R if home else 0.0
                I[m["ORN_" + ant]] = lvl
                st, l, r_, d9 = steady(I)
                rows.append(dict(antenna=ant, level=lvl, HOME_R=KN.HOME_R if home else 0.0, steer_RminusL=st, DNa_L=l, DNa_R=r_, DNp09=d9))
    return pd.DataFrame(rows), brain, steady


def crossing_level(brain, steady):
    m = brain.masks

    def f(lvl):
        I = np.zeros(brain.K)
        I[m["LC10a_R"]] = KN.HOME_R
        I[m["ORN_L"]] = lvl
        return steady(I)[0]
    lo, hi = 0.0, 60.0
    assert f(hi) < -0.01 < f(lo)
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) > -0.01 else (lo, mid)
    return hi


def main():
    import sys
    res = {}
    wfile = "W_steer_jo_orn.npy"
    dl, brain, steady = drive_levels(wfile)
    dl.to_csv(ROOT / "runs" / "M2_drive_levels.csv", index=False, lineterminator="\n")
    pd.set_option("display.width", 200)
    print(dl[dl.HOME_R > 0].pivot(index="level", columns="antenna", values="steer_RminusL").round(5).to_string())
    print(dl[dl.HOME_R == 0].pivot(index="level", columns="antenna", values="steer_RminusL").round(5).to_string())
    res["drive_home"] = dl[dl.HOME_R > 0].to_dict("records")
    L = crossing_level(brain, steady)
    # theta of the mushroom 64 px behind: Mario at x 560 (feet 176), the mushroom 16 x 16 on the ground at x 496
    from .senses import theta_of
    d = float(np.hypot(560 + 12 - (496 + 8), (176 - 16) - (176 - 8)))
    th = theta_of(d, 16)
    gain = L / th
    print(f"level at which steer (HOME_R on, left antenna) crosses -0.01: {L:.4f}; mushroom 64 px behind: eye (572, 160) to its centre (504, 168): d = {d:.3f} px, theta = {th:.5f} rad")
    print(f"SMELL_GAIN = {L:.4f} / {th:.5f} = {gain:.4f}")
    res["gain_calc"] = dict(level=L, d=d, theta=th, gain=gain)
    json.dump(res, open(ROOT / "runs" / "M2_calc.json", "w"), indent=1, default=float)
    if sys.argv[1:] == ["calc"]:
        return
    # ---- scene
    s, df = run_fly(wfile, True, record=True)
    out = csv_cols(df)
    out.to_csv(ROOT / "runs" / "M2_run.csv", index=False, lineterminator="\n")
    res["real"] = dict(hand=df.attrs["hand"], **summarise(df), left_presses_total=int(df.left.sum()))
    print("real fly:", res["real"])
    clip(df, ROOT / "clips" / "M2_smell.mp4")
    for name, kw in [("smell_off", dict(smell=False))] + [(f"shuf{i}", dict(smell=True, wfile=f"W_steer_jo_orn_shuf{i}_rn.npy")) for i in range(5)]:
        s, d = run_fly(kw.get("wfile", wfile), kw["smell"])
        res[name] = summarise(d)
        print(name, res[name])
    # no mushroom in view: any Left presses? (smell on, 200 frames)
    for name, w_ in [("real", wfile)] + [(f"shuf{i}", f"W_steer_jo_orn_shuf{i}_rn.npy") for i in range(5)]:
        s, d = run_fly(w_, True, mushroom=False, frames=200)
        res[f"nomush_{name}"] = dict(left_frames=int(d.left.sum()), left_presses=summarise(d)["left_presses"], x_end=int(d.x.iloc[-1]), a_frames=int(d.a.sum()))
        print("no mushroom,", name, res[f"nomush_{name}"])
    # noise
    rows = []
    for seed in range(1, 6):
        s, d = run_fly(wfile, True, sigma=0.05, seed=seed)
        r = summarise(d)
        rows.append(dict(seed=seed, **r))
        print("sigma 0.05 seed", seed, r)
    res["noise"] = rows
    json.dump(res, open(ROOT / "runs" / "M2_arms.json", "w"), indent=1, default=float)


def checks():
    """SMELL off: the Q2 scene (hum on, looming off) and the S3e smoke (enemies on) are button-identical on the ORN brain."""
    from . import q2_run
    out = {}
    s, df = q2_run.run_arm("W_steer_jo_orn.npy", True, bodies=BODIES)
    ref = pd.read_csv(ROOT / "runs" / "Q2_run.csv")
    n = min(len(df), len(ref))
    out["q2"] = dict(frames=(len(df), len(ref)), **{c: int((df[c].to_numpy()[:n] != ref[c].to_numpy()[:n]).sum()) for c in ("a", "right", "left")}, x_diff=int((df.x.to_numpy()[:n] != ref.x.to_numpy()[:n]).sum()))
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = "W_steer_jo_orn.npy", BODIES
    from .brain import load_brain
    from .run import run_episode
    s, d = run_episode(replace(KN, PIPE_SENSE=True, PIT_SENSE=True), load_brain(), noop_start=0, episode_seed=0)
    del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    ref = pd.read_csv(ROOT / "runs" / "S3e_full_run.csv")
    n = min(len(d), len(ref))
    out["s3e"] = dict(frames=(len(d), len(ref)), flag=s["flag_get"], max_x=s["max_x"], **{c: int((d[c].to_numpy()[:n] != ref[c].to_numpy()[:n]).sum()) for c in ("a", "right", "left")},
                      x_diff=int((d.x.to_numpy()[:n] != ref.x.to_numpy()[:n]).sum()))
    print("identity checks (SMELL off, ORN brain):", out)
    json.dump(out, open(ROOT / "runs" / "M2_checks.json", "w"), indent=1)
    return out


if __name__ == "__main__":
    import sys
    checks() if sys.argv[1:] == ["checks"] else main()
