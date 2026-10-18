"""Part C1: tables from runs/C1_arms.json (printed as markdown). python -m flyrun.c1_report"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
D = json.load(open(ROOT / "runs" / "C1_arms.json"))
kind = lambda c: "enemy" if c.startswith("enemy") else c.split(" ")[0]


def main():
    A = D["A"]
    th = [o[0] for r in A for o in r["onsets"] if o[1] in ("goomba", "koopa", "face") and o[2] is not None and o[2] >= 5]
    lo, hi, med = min(th), max(th), float(np.median(th))
    print(f"arm A trigger angle (grounded onsets on enemy/face): median {med:.1f} deg, range {lo:.1f}-{hi:.1f}, n {len(th)}\n")
    print("| arm | flags | mean max_x | mean ? blocks hit | mushroom out | mushroom eaten | big at end | mean score | deaths by cause (x) |\n|---|---|---|---|---|---|---|---|---|")
    for a in "ABC":
        R = D[a]
        dead = [r for r in R if not r["flag"]]
        causes = {}
        for r in dead:
            causes.setdefault(f"{kind(r['cause'])} @ x {r['x_end']}", 0)
            causes[f"{kind(r['cause'])} @ x {r['x_end']}"] += 1
        print(f"| {a} | {sum(r['flag'] for r in R)}/10 | {np.mean([r['max_x'] for r in R]):.0f} | {np.mean([r['n_blocks'] for r in R]):.1f} | {sum(r['mushroom_out'] for r in R)} | "
              f"{sum(r['mushroom_eaten'] for r in R)} | {sum(r['big_at_end'] for r in R)} | {np.mean([r['score'] for r in R]):.0f} | {causes or 'none'} |")
    for a in "ABC":
        print(f"\n### arm {a}\n| noop,sigma | flag | max_x | death x, cause | ? blocks hit (x) | coins | mushroom out/eaten/big at end | score | overlap jumps (hum+loom) | Left presses (mush in view / not) | A onsets with no stimulus |\n|---|---|---|---|---|---|---|---|---|---|---|")
        for r in D[a]:
            ov = r["overlap_onsets"]
            early = sum(o["theta_deg"] < lo for o in ov)
            late = sum(o["theta_deg"] > hi for o in ov)
            print(f"| {r['noop_start']},{r['sigma']} | {'flag' if r['flag'] else 'DIED'} | {r['max_x']} | {'-' if r['flag'] else str(r['x_end']) + ' ' + r['cause']} | {r['blocks_hit']} | {r['coins']} | "
                  f"{int(r['mushroom_out'])}/{int(r['mushroom_eaten'])}/{int(r['big_at_end'])} | {r['score']} | {len(ov)} (below A range {early}, above {late}) | {r['left_presses']} ({r['left_presses_mush_in_view']}/{r['left_presses_mush_not_in_view']}); frames {r['left_frames']} | {r['a_onsets_no_stimulus']} (A frames {r['a_frames_no_stimulus']}) |")
    print("\noverlap jump detail, arms B and C, episode 1 (noop 3, sigma 0):")
    for a in "BC":
        for o in D[a][0]["overlap_onsets"]:
            print(a, {k: (round(v, 1) if isinstance(v, float) else v) for k, v in o.items()})


if __name__ == "__main__":
    main()
