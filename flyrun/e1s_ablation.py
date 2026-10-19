"""E1s post-hoc ablation (NOT the official result): the best genome with SOUR_GAIN at its floor and MDN_THRESH at its upper bound (back-up nearly off), on 1-1 HOLDOUT.
python -m flyrun.e1s_ablation -> runs/E1s_ablation_holdout.json"""
import json
from pathlib import Path

from . import e1s_evolve as EV

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    genes = {g.name: g for g in EV.G.build(EV.floors())}
    values = dict(json.load(open(ROOT / "runs" / "E1s_progress.json"))["best"]["values"])
    values["SOUR_GAIN"], values["MDN_THRESH"] = genes["SOUR_GAIN"].lo, genes["MDN_THRESH"].hi
    rows = EV.holdout_episodes(values, EV.REAL)
    json.dump(dict(values=values, episodes=rows), open(ROOT / "runs" / "E1s_ablation_holdout.json", "w"), indent=1, default=float)
    print("ABLATION flags", sum(r["flag"] for r in rows), "/ 10; mean max_x", sum(r["max_x"] for r in rows) / 10, "backup presses", sum(r["backup_presses"] for r in rows))
