"""RE2 clips (R3 layout, renderer only).
python -m flyrun.re2_clips koopa_arms            -> clips/RE2_koopa_arms.mp4   arm A vs arm E side by side around the Koopa event (0.5x), 1-2 scene (replay to x 780, then the fly)
python -m flyrun.re2_clips rear_jump ARM EP      -> clips/RE2_rear_jump.mp4    one rear-loom jump on the 1-1 dev set (episode index EP), <= 8 s, 0.5x
The logs: runs/RE2_<name>.{csv,npz,json} (e1s_log.log_run)."""
import os
import sys

if len(sys.argv) > 1 and sys.argv[1] == "koopa_arms":
    os.environ["FLYRUN_LEVEL"] = "1-2"          # must be set before the first emulator use

import numpy as np

from . import e1s_clips as EC
from . import e1s_genome as G
from . import e1s_log
from . import re2_run as R
from PIL import Image, ImageDraw

from .render import panels as R3
from .render.panels import Log, Renderer, font

RUNS, CLIPS = EC.RUNS, EC.CLIPS


class SBS(EC.SideBySide2):
    """SideBySide2 with its stale captions ('start' | 'evolved', 'both from x 1000') replaced: the two bar columns are the two arms."""

    def __init__(self, specs, x0, n, names=("A", "E")):
        super().__init__(specs, x0, n)
        self.names, self.foot = names, f"0.5x speed · both from x {x0} · the same game frames (1-2 scene: L2 button replay to x 780, then the E1s champion)"

    def frame(self, i):
        img = super().frame(i)
        pil = Image.fromarray(img)
        dr = ImageDraw.Draw(pil)
        dr.rectangle([790, 183, 1140, 206], fill=R3.BG)
        dr.rectangle([300, 984, 1620, 1016], fill=R3.BG)
        dr.text((794, 186), f"arm {self.names[0]}", font=font(18), fill=(150, 150, 145))
        dr.text((980, 186), f"arm {self.names[1]}", font=font(18), fill=(150, 150, 145))
        dr.text((960, 1000), self.foot, font=font(22), fill=(150, 150, 145), anchor="mm")
        return np.asarray(pil)


def log_arm(arm, name, ep=None, takeover=None):
    base, s = e1s_log.log_run(R.champion(), name, ep=ep, takeover=takeover, prefix="RE2", knobs_fn=lambda v, a=arm: R.knobs_for(a, 0.0, v))
    print(arm, name, {k: s[k] for k in ("max_x", "end_reason", "cause", "frames")})
    return str(base)


def main_koopa_arms(x0=520):
    names = {}
    for arm in ("A", "E"):
        names[arm] = log_arm(arm, f"clip_scene_{arm}", takeover=780)
    b907 = EC.brain(G.WFILE, G.BODIES)
    thr = float(R.champion()["TTMN_THRESH"])
    specs = [("A: no rear senses (baseline)", "REAR_EYE off · REAR_SOUR off", names["A"], b907, thr),
             ("E: REAR_EYE on + REAR_SOUR honest", "behind-ticks drawn when the source is behind", names["E"], b907, thr)]
    sb = SBS(specs, x0, 250)
    sb.sides[0]["lg"].tag, sb.sides[1]["lg"].tag = "A", "E"
    EC.write((sb.frame(i) for i in range(sb.n)), CLIPS / "RE2_koopa_arms.mp4")


def main_rear_jump(arm, i):
    from . import episodes4
    e = episodes4.HOLDOUT[int(i)]
    base = log_arm(arm, f"clip_jump_{arm}_{i}", ep=dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]))
    lg = Log(base, brain=EC.brain(G.WFILE, G.BODIES))
    lg.arm, lg.tag = f"arm {arm}", f"arm {arm}, 1-1 dev episode {i}"
    d = lg.df
    on = np.flatnonzero((d.a.to_numpy() == 1) & (np.r_[0, d.a.to_numpy()[:-1]] == 0) & (d.airborne.to_numpy() == 0) & (d.threat_rear.to_numpy() == 1)) if "threat_rear" in d else []
    k = int(on[0]) if len(on) else int(np.flatnonzero(d.threat_rear.to_numpy() == 1)[0])
    s, e_ = max(0, k - 150), min(len(d) - 1, k + 150)
    rd = Renderer(lg)
    EC.write((rd.frame(nes, kk) for kk, nes in EC.replay(lg, e_) if kk >= s for _ in (0, 1)), CLIPS / "RE2_rear_jump.mp4")
    print("rear-loom jump at frame", k, "x", int(d.x.iloc[k]))


if __name__ == "__main__":
    {"koopa_arms": main_koopa_arms, "rear_jump": lambda: main_rear_jump(*sys.argv[2:4])}[sys.argv[1]]()
