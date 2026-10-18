"""python -m flyrun.render log <arm> [name]      run noop 0 sigma 0 and log rates + CSV (runs/R1_<name>.*)
python -m flyrun.render stills <name>             the four review stills of arm A (clips/R1_stills/)
python -m flyrun.render video <name> <out.mp4>    the full run"""
import sys
from pathlib import Path

import numpy as np

from . import log as L

ROOT = Path(__file__).resolve().parents[1]


def pick_frames(base):
    """(1) walking, nothing in view; (2) the first Goomba jump at GF firing; (3) a pit-tower jump at GF firing; (4) the flag."""
    from .panels import Log
    lg = Log(base)
    d, gf = lg.df, lg.gf
    walk = int(d.index[(d.threat == "none") & (d.hum_level == 0) & (d.x > 300) & (d.airborne == 0)][0])
    onset = d.index[(d.a == 1) & (d.a.shift(1, fill_value=0) == 0) & (d.airborne == 0)]
    fire = np.flatnonzero((gf[1:] >= 0.25) & (gf[:-1] < 0.25)) + 1

    def at_takeoff(kind):
        """The first grounded A press on this threat kind, moved to the GF crossing just before it (the frame the Giant Fiber fires)."""
        k = int(next(k for k in onset if d.threat[k] == kind))
        near = [int(f) for f in fire if k - 12 <= f <= k + 2]
        return near[-1] if near else k
    goomba, pit = at_takeoff("goomba"), at_takeoff("pit")
    return dict(R1_1_walking=walk, R1_2_goomba_jump=goomba, R1_3_pit_tower_jump=pit, R1_4_flag=len(d) - 1)


def main():
    a = sys.argv[1:]
    if a[0] == "log":
        L.run_log(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == "stills":
        from .video import stills
        base = ROOT / "runs" / f"R1_{a[1]}"
        fr = pick_frames(base)
        print(fr)
        stills(base, fr, ROOT / "clips" / "R1_stills", label=f"arm {a[1][-1]}   noop 0   sigma 0")
    elif a[0] == "video":
        from .video import video
        video(ROOT / "runs" / f"R1_{a[1]}", a[2], label=f"arm {a[1][-1]}   noop 0   sigma 0")


if __name__ == "__main__":
    main()
