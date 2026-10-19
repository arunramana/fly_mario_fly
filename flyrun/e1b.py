"""E1b: ablation of the E1 best genome (post-hoc, explanation only: no selection, no evolution). Same 881 brain, all four drives on.
Arms: evolved; evolved with ONE gene reset to the start value (TTMN_THRESH, SMELL_GAIN, RELEASE_THRESH, HOME_R, HUM_GAIN, STEER_THRESH); start (= arm C). Each arm on the 12 training episodes AND the 10 HOLDOUT
episodes (HOLDOUT reused for explanation only; the E1 result of 8/10 stays the official one).
python -m flyrun.e1b run | clip"""
import json
import multiprocessing as mp
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from . import e1_evolve as EV
from . import e1_genome as G
from . import episodes4

ROOT = Path(__file__).resolve().parent
EARLY_DEG = 40.0          # arm A's smallest loom trigger angle in C1 (range 40.0-97.6 deg): a hum+loom jump below it is "early"


def arms():
    genes = G.build(EV.floors())
    start = G.start_values(genes)
    best = json.load(open(ROOT / "runs" / "E1_progress.json"))["best"]["values"]
    out = {"1 evolved": dict(best)}
    for g in ("TTMN_THRESH", "SMELL_GAIN", "RELEASE_THRESH", "HOME_R", "HUM_GAIN", "STEER_THRESH"):
        out[f"- {g} reset"] = dict(best, **{g: start[g]})
    out["6 start (= arm C)"] = dict(start)
    out["extra: start + evolved TTMN_THRESH only"] = dict(start, TTMN_THRESH=best["TTMN_THRESH"])               # not in the brief: the reverse direction, 2 more arms
    out["extra: start + evolved TTMN + RELEASE"] = dict(start, TTMN_THRESH=best["TTMN_THRESH"], RELEASE_THRESH=best["RELEASE_THRESH"])
    return out


def full_episode(job):
    from . import c1_run as C
    from .run import run_episode
    arm, values, ep, kind = job
    k0, enemy_input = G.knobs_for(values)
    pr = C.Probe()
    s, df = run_episode(replace(k0, SENSOR_NOISE=ep["sigma"]), EV.brain(EV.REAL), noop_start=ep["noop_start"], episode_seed=ep["seed"], stuck_frames=150, probe=pr, enemy_input=enemy_input)
    df.attrs["hits"], df.attrs["toggles"] = pr.hits, C.toggle_set(k0, enemy_input)
    r = C.analyse(s, df, ep)
    hum = df["hum_level"].fillna(0).to_numpy() if "hum_level" in df else np.zeros(len(df))
    onset = (df.a.to_numpy() == 1) & (np.r_[0, df.a.to_numpy()[:-1]] == 0) & (df.air.to_numpy() == 0)
    r["a_nothing_in_view"] = int((onset & (df.threat_kind.to_numpy() == "none") & (hum == 0)).sum())
    r["early_hum_loom"] = int(sum(o["theta_deg"] < EARLY_DEG for o in r["overlap_onsets"]))
    r["arm"], r["kind"] = arm, kind
    for key in ("onsets", "overlap_onsets", "blocks_hit_detail"):
        r.pop(key, None)
    return r


def main_run():
    A = arms()
    eps = dict(train=EV.TRAIN12, holdout=[dict(noop_start=e["noop_start"], seed=e["seed"], sigma=e["sigma"]) for e in episodes4.HOLDOUT])
    jobs = [(a, v, ep, kind) for a, v in A.items() for kind, es in eps.items() for ep in es]
    with mp.get_context("spawn").Pool(EV.NPROC) as pool:
        res = pool.map(full_episode, jobs, chunksize=1)
    json.dump(dict(arms=A, episodes=res), open(ROOT / "runs" / "E1b_episodes.json", "w"), indent=1, default=float)
    print(len(res), "episodes")


def main_clip():
    """10 s contrast at the hum + Goomba spot (x ~1220): arm 2 (TTMN_THRESH reset) then arm 1 (evolved), noop 0 sigma 0, R3 layout."""
    import cv2
    from .render import log as RL
    from .render.panels import Log, Renderer
    from .render.video import replay
    A = arms()
    parts = []
    for label, vals in (("evolved, TTMN_THRESH reset to 0.10", A["- TTMN_THRESH reset"]), ("evolved (TTMN_THRESH 0.1275)", A["1 evolved"])):
        name = "E1b_" + ("ttmn_reset" if "reset" in label else "evolved")
        RL.run_log("C", name, prefix="E1b", overrides=vals, brain=EV.brain(EV.REAL))
        lg = Log(str(ROOT / "runs" / f"E1b_{name}"))
        lg.arm = label
        x = lg.df.x.to_numpy()
        i0 = int(np.argmax(x >= 1120))
        i1 = int(min(len(x) - 1, i0 + 300))
        parts.append((lg, max(0, i0 - 30), i1))
    vw = cv2.VideoWriter(str(ROOT / "clips" / "E1b_threshold.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 60, (1920, 1080))
    n = 0
    for lg, k0, k1 in parts:
        rd = Renderer(lg)
        for k, nes in replay(lg, k1):
            if k >= k0:
                vw.write(cv2.cvtColor(rd.frame(nes, k), cv2.COLOR_RGB2BGR))
                n += 1
    vw.release()
    print("clip", n, "frames = %.1f s" % (n / 60), [(lg.arm, k0, k1, len(lg)) for lg, k0, k1 in parts])


if __name__ == "__main__":
    {"run": main_run, "clip": main_clip}[sys.argv[1]]()
