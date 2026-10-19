"""E1s section 2: the gain floors on the 907-neuron sour brain (log bisections of yes / no scenes; the other genes at the E1 best / AV1 values where the scene uses them).
 HUM_GAIN: hum alone (Q2 scene) still hits block 256. SMELL_GAIN: smell alone, home off (M2b scene A) still turns him (>= 5 Left frames). HOME_R: nothing in view, Right pressed in >= 95% of frames 30-300.
 SOUR_GAIN: the AV1 Koopa scene (1-2, replay to x 780, sour + headroom on, E1 genome) still backs up (>= 5 back-up frames).
python -m flyrun.e1s_floors -> runs/E1s_floors.json"""
import json
import os
import subprocess
import sys
from pathlib import Path

from . import e1_floors as F
from . import e1s_genome as G

ROOT = Path(__file__).resolve().parent


def sour_backs_up(g):
    env = dict(os.environ, AV1_TAKEOVER="780", PYTHONPATH=str(ROOT.parent))
    subprocess.run([sys.executable, "-m", "flyrun.av1_run", "scene", "E1sfloor", G.WFILE, "1", "1", repr(g)], env=env, capture_output=True, cwd=str(ROOT.parent))
    return json.load(open(ROOT / "runs" / "AV1_E1sfloor_scene.json")).get("backup_frames", 0) >= 5


def main():
    from . import m2_run as M
    F.WF, F.BODIES, M.BODIES = G.WFILE, G.BODIES, G.BODIES
    out = {}
    for name, hi, lo, fn in (("HUM_GAIN", 14.5342, 0.5, F.hum_hits_256), ("SMELL_GAIN", 213.9495, 2.0, F.smell_turns), ("HOME_R", 0.5, 0.005, F.home_walks), ("SOUR_GAIN", 8.0587, 0.2, sour_backs_up)):
        v, how = F.bisect(lo, hi, fn)
        out[name] = dict(search_hi=hi, floor=v, how=how, search_lo=lo)
        print(name, out[name], flush=True)
    json.dump(out, open(ROOT / "runs" / "E1s_floors.json", "w"), indent=1)


if __name__ == "__main__":
    main()
