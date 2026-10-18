"""Part O0 sections 3 and 5.
3. Motor check: can the fly go LEFT? Scratch runs only: the default brain (and, separately, the scratch ORN build) driven with HOME_R on, plus a steering input;
   motor v2 turns the brain state into buttons; the emulator (enemies removed) shows what Mario does.
5. Baseline (no new senses): the S3e fly (looming on, default knobs, senses v2 + motor v2) with enemies removed, start -> x 650, and from the mushroom-behind setup.
python -m flyrun.o0_motor"""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E
from . import level, motor
from .brain import load_brain
from .knobs import Knobs
from .o0_ram import ADDR_ACTIVE, ADDR_POWERUP, MUSHROOM_SLOT, Sim, hit_from_below
from . import o0_sim as S

ROOT = Path(__file__).resolve().parent
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0)
NAMES = {E.NOOP: "none", E.RIGHT: "Right", E.RIGHT_A: "Right+A", E.LEFT: "Left", E.LEFT_A: "Left+A"}


def drive_run(net, I_fn, frames, pre=150, post_label=""):
    """pre frames with HOME_R only (Mario walks right), then `frames` frames with I_fn(); enemies removed. -> summary dict."""
    sim = Sim(remove=True)
    h = np.zeros(net.K)
    mus = motor.Muscle2()
    masks = net.m
    rows = []
    for f in range(pre + frames):
        I = I_fn(f - pre) if f >= pre else net.vec(LC10a_R=S.HOME_R)
        for _ in range(S.SUBSTEPS):
            h = (1 - S.ALPHA) * h + S.ALPHA * np.clip(S.G * (net.W @ h) + I, 0.0, S.CLIP)
        action, read = motor.decide(h, masks, KN, mus, airborne=int(sim.ram[0x001D]) != 0)
        x_before = sim.mx
        done, _ = sim.step(action)
        rows.append(dict(frame=f, phase="post" if f >= pre else "pre", x=sim.mx, action=NAMES[action], steer=read["steer"], dnp09=read["dnp09"],
                         dna_l=float(h[masks["DNa_L"]].mean()), dna_r=float(h[masks["DNa_R"]].mean())))
        if done:
            break
    df = pd.DataFrame(rows)
    post = df[df.phase == "post"]
    return dict(x_start=int(post.x.iloc[0]), x_end=int(post.x.iloc[-1]), x_min=int(post.x.min()), dx=int(post.x.iloc[-1] - post.x.iloc[0]),
                steer_mean=float(post.steer.mean()), steer_last=float(post.steer.iloc[-1]), dnp09_mean=float(post.dnp09.mean()),
                frac_Left=float(post.action.isin(["Left", "Left+A"]).mean()), frac_Right=float(post.action.isin(["Right", "Right+A"]).mean()),
                frac_none=float((post.action == "none").mean()), buttons=post.action.value_counts().to_dict(), died=bool(done))


def part3():
    out = {}
    brain = load_brain()
    W, bodies = S.build([])
    base = S.Net(W, bodies)
    assert np.abs(W - brain.W).max() == 0
    # (a) the default brain, steering injected straight into DNa_L (a scratch current; nothing like it exists in the shipped fly)
    rows = []
    for c in (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0):
        r = drive_run(base, lambda f, c=c: base.vec(LC10a_R=S.HOME_R, DNa_L=c), 150)
        rows.append(dict(DNa_L_current=c, **r))
    a = pd.DataFrame(rows)
    pd.set_option("display.width", 250)
    print("(a) default brain, HOME_R 0.5 + a current into DNa_L (150 frames after 150 frames of walking right):")
    print(a.drop(columns=["buttons"]).to_string(index=False))
    out["inject_DNa_L"] = rows
    a.drop(columns=["buttons"]).to_csv(ROOT / "runs" / "O0_motor_dnaL.csv", index=False, lineterminator="\n")
    # (b) the scratch ORN build: left-antenna attractive ORNs on top of HOME_R (what smell would do)
    ATTR = ["ORN_DM1", "ORN_VA2", "ORN_DM4"]
    orn_mask = np.isin(S.TYPES, ATTR)
    kn = S.kn_new_ids(orn_mask, np.isin(S.TYPES, ["DNa01", "DNa02"]))
    net = S.Net(*S.build(list(kn)))
    idxL = np.flatnonzero(np.isin(net.b.bodyId.to_numpy(), S.IDS[orn_mask & (S.SIDE == "L")]))
    rows = []
    for lvl in (0, 20, 50, 100, 200):
        def fn(f, lvl=lvl):
            I = net.vec(LC10a_R=S.HOME_R)
            I[idxL] = lvl
            return I
        r = drive_run(net, fn, 150)
        rows.append(dict(left_ORN_level=lvl, **r))
    b = pd.DataFrame(rows)
    print("(b) scratch ORN build, HOME_R 0.5 + left-antenna attractive ORNs:")
    print(b.drop(columns=["buttons"]).to_string(index=False))
    out["left_ORN"] = rows
    b.drop(columns=["buttons"]).to_csv(ROOT / "runs" / "O0_motor_orn.csv", index=False, lineterminator="\n")
    return out


def _run_fly(prefix, max_x, max_frames, watch):
    """The S3e fly from the current emulator state (a prefix may have run). Enemies removed after every step. -> (summary, df, trace)."""
    from . import run as R
    env = R._get_env()
    ram = env.unwrapped.ram
    orig_step, orig_reset = env.step, env.reset
    trace = []
    if prefix is not None:
        env.unwrapped._backup()
        env.reset = lambda *a, **k: (env.unwrapped._restore(), np.asarray(env.unwrapped.screen).copy())[1]

    def step(action):
        out = orig_step(action)
        for s in range(5):
            ram[ADDR_ACTIVE + s] = 0
        trace.append(dict(x=E.mario_x(ram), tiles={w: (level.tile(ram, w, 7) if level._visible_range(ram)[0] <= w < level._visible_range(ram)[1] - 16 else None) for w in watch}, powerup=int(ram[ADDR_POWERUP]), mushroom=bool(ram[ADDR_ACTIVE + MUSHROOM_SLOT]),
                          mushroom_x=int(ram[0x6E + MUSHROOM_SLOT]) * 256 + int(ram[0x87 + MUSHROOM_SLOT]) if ram[ADDR_ACTIVE + MUSHROOM_SLOT] else None))
        if E.mario_x(ram) >= max_x:
            return out[0], out[1], True, out[3]
        return out
    env.step = step
    try:
        s, df = R.run_episode(KN, load_brain(), noop_start=0, max_frames=max_frames, stuck_frames=10 ** 6)
    finally:
        del env.step
        if prefix is not None:
            del env.reset
    return s, df, pd.DataFrame(trace)


def part5():
    out = {}
    # A: from the start, enemies removed, to x 650: any "?" hit? mushroom? eaten?
    s, df, tr = _run_fly(None, 650, 1500, (256, 336, 368))
    hit = {w: bool(any(t[w] in (35, 196) for t in tr.tiles)) for w in (256, 336, 368)}   # bump (35) / used (196) while the block is on screen
    print("A: fly, enemies removed, from the start: x_end", s["max_x"], "frames", s["frames"], "A frac %.2f" % s["a_frac"], "left presses", s.get("left_presses"),
          "| ? hit (tile changed):", hit, "| mushroom ever active:", bool(tr.mushroom.any()), "| power-up state max:", int(tr.powerup.max()))
    out["A"] = dict(x_end=s["max_x"], frames=s["frames"], a_frac=s["a_frac"], left_presses=s.get("left_presses"), hit=hit, mushroom=bool(tr.mushroom.any()), powerup_max=int(tr.powerup.max()),
                    jumps_at_x=[int(x) for x in df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0) & (df.air == 0)].x])
    print("   jump take-offs at x:", out["A"]["jumps_at_x"])
    # B: M2 setup (scripted hit, scripted run to x 560, mushroom re-placed 64 px behind, moving right), then the fly
    from . import scripted
    sim = Sim(remove=True)
    hit_from_below(sim, 336)
    drv = scripted.Driver()
    for f in range(1200):
        if sim.mx >= 560 and int(sim.ram[0x001D]) == 0 and sim.powerup():
            break
        sim.step(drv.act(sim.ram))
    x = sim.mx - 64
    r, sl = sim.ram, MUSHROOM_SLOT
    r[0x6E + sl], r[0x87 + sl], r[0xCF + sl], r[0x46 + sl], r[0x58 + sl] = x // 256, x % 256, 184, 1, 16
    mx0, mush0 = sim.mx, sim.powerup()
    s, df, tr = _run_fly(True, 1700, 900, ())
    turned = int((df.left == 1).sum())
    print("B: M2 placed setup: hand-over Mario x", mx0, "mushroom", mush0["x"], "->", "fly: x_end", s["max_x"], "min x", int(df.x.min()), "left presses", s.get("left_presses"), "left frames", int(df.left.sum()),
          "| power-up max", int(tr.powerup.max()), "| mushroom active at end:", bool(tr.mushroom.iloc[-1]), "| mushroom x at 30/60/90:", [tr.mushroom_x.iloc[i] if i < len(tr) else None for i in (30, 60, 90)])
    out["B"] = dict(handover_mario_x=mx0, mushroom=mush0, x_end=s["max_x"], x_min=int(df.x.min()), left_presses=s.get("left_presses"), left_frames=turned, powerup_max=int(tr.powerup.max()),
                    mushroom_x_track=[None if pd.isna(v) else int(v) for v in tr.mushroom_x.iloc[::30]], end=s["end_reason"], cause=s["cause"])
    return out


def main():
    import sys
    if sys.argv[1:] == ["baseline"]:                 # re-run only section 5 (merge into the saved json)
        old = json.load(open(ROOT / "runs" / "O0_motor.json"))
        old["baseline"] = part5()
        json.dump(old, open(ROOT / "runs" / "O0_motor.json", "w"), indent=1, default=float)
        return
    out = {"motor": part3(), "baseline": part5()}
    json.dump(out, open(ROOT / "runs" / "O0_motor.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
