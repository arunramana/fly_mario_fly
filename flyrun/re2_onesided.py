"""RE2 section 1 (fact check, scratch, default brain untouched): drive only the LEFT DC4 ORNs, only the RIGHT ones, then both, in the 907 sour brain.
Steady drive, 100 frames x 10 substeps, the E1s champion's motor/home genes (HOME_R into LC10a-R as in the game). Reports MDN, DNa_R - DNa_L (steer) and DNp09.
python -m flyrun.re2_onesided -> runs/RE2_onesided_sour.json"""
import json
from pathlib import Path

import numpy as np

from . import av1_run as A
from . import e1s_genome as G
from . import re2_run as R
from .brain import step

ROOT = Path(__file__).resolve().parent


def steady(net, k, level_l, level_r, home=True, frames=100):
    m = net.masks
    h = np.zeros(net.K)
    I = np.zeros(net.K)
    if home:
        I[m["LC10a_R"]] = k.HOME_R
    I[m["DC4_L"]] = level_l
    I[m["DC4_R"]] = level_r
    for _ in range(frames):
        for _ in range(k.SUBSTEPS):
            h = step(h, net.W, k.G, I, k.ALPHA, k.CLIP)
    return dict(MDN=float(h[m["MDN"]].mean()), DNa_L=float(h[m["DNa_L"]].mean()), DNa_R=float(h[m["DNa_R"]].mean()), steer=float(h[m["DNa_R"]].mean() - h[m["DNa_L"]].mean()), DNp09=float(h[m["DNp09"]].mean()),
                MDN_each=[round(float(x), 4) for x in h[m["MDN"]]])


def main():
    net = A.brain(G.WFILE)
    k, _ = R.knobs_for("A")
    gain = float(k.SOUR_GAIN)
    out = dict(n_DC4_L=int(net.masks["DC4_L"].sum()), n_DC4_R=int(net.masks["DC4_R"].sum()), n_MDN=int(net.masks["MDN"].sum()), SOUR_GAIN=gain, HOME_R=float(k.HOME_R), STEER_THRESH=float(k.STEER_THRESH), MDN_THRESH=float(k.MDN_THRESH), rows=[])
    print({kk: v for kk, v in out.items() if kk != "rows"})
    for home in (True, False):
        for deg in (20, 43.6, 50, 70, 90):
            lvl = gain * np.radians(deg)
            for side, (l, r) in (("left only", (lvl, 0.0)), ("right only", (0.0, lvl)), ("both", (lvl, lvl))):
                row = dict(home=home, theta_deg=deg, level=lvl, side=side, **steady(net, k, l, r, home))
                out["rows"].append(row)
                print(f"home={int(home)} theta {deg:5.1f} level {lvl:6.3f} {side:10s} MDN {row['MDN']:.4f}  steer(R-L) {row['steer']:+.5f}  DNa_L {row['DNa_L']:.4f} DNa_R {row['DNa_R']:.4f}  DNp09 {row['DNp09']:.4f}")
    json.dump(out, open(ROOT / "runs" / "RE2_onesided_sour.json", "w"), indent=1)


if __name__ == "__main__":
    main()
