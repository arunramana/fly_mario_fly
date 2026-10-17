"""Fix 1 diagnosis: 7e final genome, HOLDOUT ep0 (noop 3, seed 101, sigma 0), frames -60..death with both Goombas and Mario's state.
Extra RAM read after each step: player state 0x0E (0x0B = dying), Mario y-speed 0x9F, enemy state 0x1E+slot, enemy flag. Wrapper only."""
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from . import env as E
from . import part7 as P
from .brain import load_brain
from .diagnose7b import capture

ROOT = Path(__file__).resolve().parent
ADDR_PSTATE, ADDR_YSPEED, ADDR_ESTATE = 0x000E, 0x009F, 0x001E


def run(cfg, genome_path, ep_i=0, knobs_override=None):
    g = json.loads(Path(genome_path).read_text(encoding="utf-8"))
    knobs, _ = P.decode(cfg, g["u"])
    if knobs_override:
        knobs = replace(knobs, **knobs_override)
    ep = cfg["episodes"]["holdout"][ep_i]
    def extra(ram):
        ys = int(ram[ADDR_YSPEED])
        return (int(ram[ADDR_PSTATE]), ys - 256 if ys > 127 else ys,
                " ".join(f"s{s}:st{int(ram[ADDR_ESTATE + s]):02X}" for s in range(E.N_ENEMY_SLOTS)
                         if int(ram[E.ADDR_ENEMY_ACTIVE + s]) and int(ram[E.ADDR_ENEMY_TYPE + s]) != E.POWERUP_ID))
    s, d = capture(replace(knobs, SENSOR_NOISE=float(ep["sigma"])), ep, load_brain(), extra=extra)
    d["pstate_after"] = [e[0] for e in d["extra"]]
    d["yspeed_after"] = [e[1] for e in d["extra"]]
    d["estate_after"] = [e[2] for e in d["extra"]]
    return s, d


if __name__ == "__main__":
    cfg = P.load_config(ROOT / "configs" / "part7.yaml")
    s, d = run(cfg, ROOT / "runs" / "008e_final_genome.json")
    print(s["max_x"], s["cause"], len(d))
    cols = ["frame", "x", "y", "air", "a", "a_left", "cool_left", "ttmn", "stim_src", "stim_d", "enemies", "pstate_after", "yspeed_after", "estate_after"]
    print(d.iloc[-61:][cols].to_string())
    d.iloc[-61:][cols].to_csv(ROOT / "runs" / "009_death_last60.csv", index=False, lineterminator="\n")
