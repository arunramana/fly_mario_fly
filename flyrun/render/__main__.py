"""python -m flyrun.render log <arm> [name]      run noop 0 sigma 0 and log rates + CSV (runs/R1_<name>.*)
python -m flyrun.render stills <name>             the four review stills of arm A (clips/R1_stills/)
python -m flyrun.render video <name> <out.mp4>    the full run"""
import sys
from pathlib import Path

import numpy as np

from . import log as L

ROOT = Path(__file__).resolve().parents[1]


def pick_frames(base):
    """The first Goomba jump (the frame the Giant Fiber fires) and the pit-tower jump of arm A."""
    from .panels import Log
    lg = Log(base)
    d = lg.df
    goomba = next(f for f in lg.fire if d.threat[f] == "goomba")
    pit = next(f for f in lg.fire if d.threat[f] == "pit")
    return dict(R3_1_goomba_jump=goomba, R3_2_pit_tower_jump=pit)


def pick_frames_c(base):
    """Arm C: the first frame after the mushroom block (x 336) is hit where the hum (the next block) and the smell (the mushroom) are both on."""
    from .panels import Log
    d = Log(base).df
    k = int(d.index[(d.blocks_hit >= 1) & (d.hum_level > 0) & ((d.smell_L > 0) | (d.smell_R > 0))][0]) + 14
    return dict(R3_3_armC_hum_smell=k)


def main():
    a = sys.argv[1:]
    if a[0] == "log":
        L.run_log(a[1], a[2] if len(a) > 2 else None)
    elif a[0] == "stills":
        from .video import stills
        base = ROOT / "runs" / f"R1_{a[1]}"
        fr = pick_frames(base) if a[1] == "armA" else pick_frames_c(base)
        print(fr)
        stills(base, fr, ROOT / "clips" / "R3_stills")
        if a[1] == "armA":
            from .panels import Log, title_card
            title_card(Log(base), ROOT / "clips" / "R3_title_card.png")
    elif a[0] == "video":
        from .video import video
        video(ROOT / "runs" / f"R1_{a[1]}", a[2], )


if __name__ == "__main__":
    main()
