"""Part Q1 section 2 (measurement, no tuning loop): the hit window of the "?" block at x 256, the hum -> TTMn curve, and HUM_GAIN chosen ONCE.
python -m flyrun.q1_calibrate    -> runs/Q1_window.csv, runs/Q1_hum_curve.csv, prints the calculation."""
import os
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

os.environ["FLYRUN_WFILE"] = "W_steer_jo.npy"
os.environ["FLYRUN_BODIES"] = "steer_jo_bodies.parquet"
from . import env as E  # noqa: E402
from . import level, senses_v2 as SV  # noqa: E402
from .brain import load_brain, step  # noqa: E402
from .knobs import Knobs  # noqa: E402
from .o0_ram import Sim  # noqa: E402

ROOT = Path(__file__).resolve().parent
BLOCK_X = 256
KN = replace(Knobs(), SENSES_VERSION="v2", MOTOR_VERSION="v2", SENSOR_NOISE=0.0, HUM_SENSE=True, HUM_GAIN=1.0)


def hit_window():
    """Scripted, no fly: walk right at the normal walking speed (Right only), take off when his left edge is `off` px from the block's left edge
    (off < 0: before it), hold Right+A until the head bump (tile 192 -> 35) or the landing. -> DataFrame."""
    rows = []
    for off in range(-60, 33):
        sim = Sim(remove=True)
        while sim.mx < BLOCK_X + off:
            sim.step(E.RIGHT)
        x0 = sim.mx
        hit, f, air = False, 0, False
        for f in range(70):
            sim.step(E.RIGHT_A)
            air = air or int(sim.ram[0x001D]) != 0
            if level.tile(sim.ram, BLOCK_X, 7) != 192:
                hit = True
                break
            if air and int(sim.ram[0x001D]) == 0:
                break
        rows.append(dict(takeoff_x=x0, offset_from_block_left=x0 - BLOCK_X, hit=hit, frames_held=f + 1, feet_at_end=int(sim.ram[0xCE])))
    return pd.DataFrame(rows).drop_duplicates("takeoff_x")


def hum_curve(gain):
    """TTMn vs x while he WALKS in (Right only, no A): the brain's dynamics driven by HOME_R + the hum at `gain`, step by step along the walk."""
    brain = load_brain()
    kn = replace(KN, HUM_GAIN=gain)
    sim = Sim(remove=True)
    se = SV.SensesV2(kn, brain.masks, brain.K)
    h = np.zeros(brain.K)
    rows = []
    for f in range(400):
        if sim.mx > BLOCK_X + 70:
            break
        I, lm = se.look(sim.ram)
        for _ in range(kn.SUBSTEPS):
            h = step(h, brain.W, kn.G, I, kn.ALPHA, kn.CLIP)
        ttmn = float(h[brain.masks["TTMn"]].mean())
        rows.append(dict(frame=f, x=sim.mx, hum_level=lm.extra["hum_level"], ttmn=ttmn, gf=float(h[brain.masks["TTMn"]].mean())))
        sim.step(E.RIGHT)
    return pd.DataFrame(rows)


def main():
    w = hit_window()
    w.to_csv(ROOT / "runs" / "Q1_window.csv", index=False, lineterminator="\n")
    hits = w[w.hit]
    print("hit window (one jump, Right+A held until the head bump):")
    print(w[["takeoff_x", "offset_from_block_left", "hit", "frames_held"]].to_string(index=False))
    lo, hi = int(hits.offset_from_block_left.min()), int(hits.offset_from_block_left.max())
    contiguous = len(hits) == hi - lo + 1 or None
    print(f"window: take-off offset {lo} .. {hi} px from the block's left edge ({len(hits)} take-off positions, x {int(hits.takeoff_x.min())}..{int(hits.takeoff_x.max())}); middle = {(lo + hi) / 2}")
    mid_x = BLOCK_X + int(round((lo + hi) / 2))
    c1 = hum_curve(1.0)
    c0 = hum_curve(0.0)                    # the same walk with the hum muted: HOME_R only (the brain's own transient, so the base is exact)
    c1.to_csv(ROOT / "runs" / "Q1_hum_curve.csv", index=False, lineterminator="\n")
    i = int(np.flatnonzero(c1.x.to_numpy() >= mid_x)[0])
    u, base, lvl = float(c1.ttmn.iloc[i]), float(c0.ttmn.iloc[i]), float(c1.hum_level.iloc[i])
    print(f"unit-gain curve at the walk-in position x {int(c1.x.iloc[i])} (offset {int(c1.x.iloc[i]) - BLOCK_X}): hum level {lvl:.4f} (theta_block {lvl:.4f} rad), TTMn(g=1) {u:.6f}, TTMn(g=0) {base:.6f}")
    thr = Knobs().TTMN_THRESH
    g = (thr - base) / (u - base)
    print(f"HUM_GAIN = (TTMN_THRESH {thr} - TTMn(g=0) {base:.6f}) / (TTMn(g=1) - TTMn(g=0) = {u - base:.6f}) = {g:.4f}   (the network is linear here: TTMn(x; g) = TTMn(x; 0) + g (TTMn(x; 1) - TTMn(x; 0)))")
    c = hum_curve(g)
    cross = c[c.ttmn >= thr].iloc[0]
    print(f"check at that gain: TTMn first >= {thr} at x {int(cross.x)} (offset {int(cross.x) - BLOCK_X}), target offset {mid_x - BLOCK_X}; TTMn there {cross.ttmn:.4f}")
    print("curve at that gain, every 3rd position:", [(int(x) - BLOCK_X, round(t, 4)) for x, t in zip(c.x.iloc[::3], c.ttmn.iloc[::3]) if BLOCK_X - 60 <= x <= BLOCK_X])
    return g


if __name__ == "__main__":
    main()
