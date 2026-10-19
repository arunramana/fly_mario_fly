"""AV1 step 2: set SOUR_GAIN once. The sour input is level = SOUR_GAIN x theta_enemy into every DC4 ORN (both antennae). Choose SOUR_GAIN so that MDN (mean of the 4) crosses MDN_THRESH = 0.10
at theta_enemy = 50 deg, just past the looming trigger (43.6 deg): level* / theta*, level* = the steady drive (HOME_R on, E1 genome, 100 frames) at which MDN = 0.10 (bisection).
Then a check with the approach dynamics (theta rising as an enemy closes in, no other drive). python -m flyrun.av1_gain -> runs/AV1_sour_gain.json (FROZEN afterwards)"""
import json
import os
from pathlib import Path

import numpy as np

from . import av1_run as R

ROOT = Path(__file__).resolve().parent


def run(net, k, I_of_f, frames):
    h = np.zeros(net.K)
    out = []
    for f in range(frames):
        I = I_of_f(f)
        from .brain import step
        for _ in range(k.SUBSTEPS):
            h = step(h, net.W, k.G, I, k.ALPHA, k.CLIP)
        out.append(float(h[net.masks["MDN"]].mean()))
    return np.array(out)


def main():
    net = R.brain("W_steer_jo_orn_sour.npy")
    k, _ = R.knobs_for(True, False, gain=0.0)
    theta50 = np.radians(50.0)

    def steady(level, frames=100):
        def I_of(f):
            I = np.zeros(net.K)
            I[net.masks["LC10a_R"]] = k.HOME_R
            I[net.masks["DC4_L"]] = I[net.masks["DC4_R"]] = level
            return I
        return run(net, k, I_of, frames)

    lo, hi = 0.0, 200.0
    print("MDN at rest (level 0):", steady(0.0)[-1], "| at 200:", steady(200.0)[-1])
    for _ in range(40):
        mid = (lo + hi) / 2
        if steady(mid)[-1] >= 0.10:
            hi = mid
        else:
            lo = mid
    level_star = hi
    gain = level_star / theta50
    print(f"steady drive at which MDN = 0.100: level* = {level_star:.4f}; theta* = 50 deg = {theta50:.4f} rad; SOUR_GAIN = level*/theta* = {gain:.4f}")
    rows = []
    for deg in (20, 30, 40, 43.6, 45, 50, 55, 60, 70, 90):
        lvl = gain * np.radians(deg)
        rows.append(dict(theta_deg=deg, level=float(lvl), MDN_steady=float(steady(lvl)[-1])))
        print(f"  theta {deg:5.1f} deg  level {lvl:7.3f}  MDN (steady, 100 frames) {rows[-1]['MDN_steady']:.4f}")
    # dynamics: a 16-px Goomba (h 16) closing from d = 80 px to 8 px at 0.9 px/frame (his walk 1.3 px/frame + the Goomba 0.6 px/frame => ~1.9 px/frame; also 1.9 used), theta = 2 atan(8 / d)
    dyn = {}
    for v in (0.9, 1.9):
        d = np.maximum(80.0 - v * np.arange(80), 8.0)
        th = 2 * np.arctan(8.0 / d)
        m = run(net, k, lambda f: (lambda I: (I.__setitem__(net.masks["LC10a_R"], k.HOME_R), I.__setitem__(net.masks["DC4_L"], gain * th[f]), I.__setitem__(net.masks["DC4_R"], gain * th[f]), I)[-1])(np.zeros(net.K)), len(d))
        cross = np.flatnonzero(m >= 0.10)
        dyn[str(v)] = dict(first_frame_over=int(cross[0]) if len(cross) else None, theta_deg_at_cross=float(np.degrees(th[cross[0]])) if len(cross) else None, MDN_peak=float(m.max()))
        print(f"  approach at {v} px/frame: MDN crosses 0.10 at theta {dyn[str(v)]['theta_deg_at_cross']} deg (frame {dyn[str(v)]['first_frame_over']}), peak {m.max():.3f}")
    json.dump(dict(SOUR_GAIN=float(gain), level_star=float(level_star), theta_star_deg=50.0, MDN_THRESH=0.10, HOME_R=k.HOME_R, table=rows, dynamic=dyn), open(ROOT / "runs" / "AV1_sour_gain.json", "w"), indent=1)


if __name__ == "__main__":
    main()
