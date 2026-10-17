"""Part 6b: re-render only what changed. Clip 06 (typical shuffle, median HOLDOUT episode), clips/07_results_card.png,
and the numbers.md additions (invented pieces, sha256 of every array, distinct trajectories).
python -m flyrun.make_clips6b"""
import hashlib
import json
import shutil
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .brain import CACHE, Brain, load_brain
from .episodes4 import HOLDOUT
from .evolve6 import EVO6
from .genome import decode
from .knobs import INVENTED
from .make_clips import CLIPS, DATA, Panel, fly_clip, run

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
MARK = "## Invented pieces"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fair():
    return (json.loads((RUNS / "007_fair_eval.json").read_text()),
            json.loads((RUNS / "007_default_knobs.json").read_text()))


def clip06(fe):
    seeds = [0, 1, 2]
    sc = {s: fe[f"shuf{s}_rn/evolved_best"]["mean_max_x"] for s in seeds}
    seed = sorted(seeds, key=sc.get)[1]                       # the MEDIAN seed by evolved HOLDOUT mean max_x
    arm = f"shuf{seed}_rn"
    mx = fe[f"{arm}/evolved_best"]["max_x"]
    ep_i = int(np.argsort(mx, kind="stable")[len(mx) // 2])   # the median HOLDOUT episode of that seed
    ep = HOLDOUT[ep_i]
    g = decode("fly", np.array(json.loads((EVO6 / arm / "best_genome.json").read_text())["u"]))[0]
    brain = load_brain()
    sb = Brain(W=np.load(CACHE / f"W_steer_{arm}.npy"), bodies=brain.bodies, masks=brain.masks)
    s, df = run(g, sb, ep=ep)
    df.to_csv(DATA / "shuffle_median_log.csv", index=False)
    old = CLIPS / "06_shuffle.mp4"
    if old.exists():
        shutil.move(str(old), str(CLIPS / "06_shuffle_SUPERSEDED_best_of_40_part5.mp4"))
    n = fly_clip(CLIPS / "06_shuffle.mp4", df, Panel(sb), 0, len(df),
                 f"SHUFFLED wiring (rows re-normalised), seed {seed}, its evolved genome, HOLDOUT nstart {ep['noop_start']} sigma {ep['sigma']}",
                 banner=f"CONTROL | degree-shuffled connectome | MEDIAN of 10 HOLDOUT episodes (median seed {seed})")
    return [("shuffle seed (median of 0-2 by evolved HOLDOUT mean max_x)", seed), ("episode (median max_x of 10)", str(ep)),
            ("max_x", s["max_x"]), ("end", f"{s['end_reason']} ({s['cause']})"),
            ("blind presses", f"{s['blind_presses']} of {s['n_onsets']}"),
            ("that seed's HOLDOUT mean max_x / distinct trajectories", f"{sc[seed]:.0f} / {fe[arm + '/evolved_best']['n_traj']} of 10"),
            ("selection", "typical, not best: replaces Part 5's best-of-40 clip"), ("clip frames", n)]


def card(fe, dk):
    rows = []   # (label, mean, lo, hi, trajectories text, kind)

    sil = json.loads((RUNS / "007_silence.json").read_text())
    extra = {"real wiring, evolved (equal budget)": f"looming escape 10/10 | A with nothing in view: {sil['real']['silence_a_frac']:.0%}",
             "real wiring, default knobs": "looming escape 10/10 | first A at theta 43.6 deg",
             "shuffled, 3 seeds, each evolved": "looming escape 0/30 | A, nothing in view: " + "/".join(f"{sil[f'shuf{i}_rn']['silence_a_frac']:.0%}" for i in range(3)),
             "shuffled, 5 seeds, default knobs": "escape 0/4 seeds (seed 4 presses A from frame 0, no stimulus)",
             "evolved timer (no brain)": "no sensing at all", "theta rule (no brain)": "no brain; reads theta"}

    def add(label, vals, trajs, kind):
        rows.append((label, float(np.mean(vals)), min(vals), max(vals), trajs, kind, extra[label]))

    add("real wiring, evolved (equal budget)", [fe["real/evolved_best"]["mean_max_x"]], str(fe["real/evolved_best"]["n_traj"]), "real")
    add("real wiring, default knobs", [dk["real"]["holdout_mean_max_x"]], str(dk["real"]["n_traj"]), "real")
    sv = [fe[f"shuf{i}_rn/evolved_best"] for i in range(3)]
    add("shuffled, 3 seeds, each evolved", [v["mean_max_x"] for v in sv], "/".join(str(v["n_traj"]) for v in sv), "shuf")
    sd = [dk[f"shuf{i}_rn"] for i in range(5)]
    add("shuffled, 5 seeds, default knobs", [v["holdout_mean_max_x"] for v in sd], "/".join(str(v["n_traj"]) for v in sd), "shuf")
    add("evolved timer (no brain)", [fe["timer_evolved"]["mean_max_x"]], str(fe["timer_evolved"]["n_traj"]), "base")
    add("theta rule (no brain)", [fe["theta_rule_evolved"]["mean_max_x"]], str(fe["theta_rule_evolved"]["n_traj"]), "base")
    col = {"real": "#2a6fdb", "shuf": "#d9822b", "base": "#8a8f98"}
    fig, ax = plt.subplots(figsize=(11, 6.6), dpi=130)
    y = np.arange(len(rows))[::-1]
    for yi, (lab, m, lo, hi, tr, kind, ex) in zip(y, rows):
        ax.barh(yi, m, color=col[kind], height=0.55)
        if hi > lo:
            ax.plot([lo, hi], [yi, yi], color="#222", lw=1.6)
            ax.plot([lo, hi], [yi, yi], "|", color="#222", ms=9)
        ax.text(max(hi, m) + 40, yi, f"{m:,.0f}   distinct trajectories of 10: {tr}\n{ex}", va="center", fontsize=8.5, color="#222")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xlim(0, 6200)
    ax.set_xlabel("HOLDOUT mean max_x (px); 10 held-out start timings on level 1-1; line = range across seeds", fontsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("Real wiring vs fair (row-renormalised) shuffle vs no-brain baselines", loc="left", fontsize=13)
    inv = "INVENTED, not from the connectome: " + ", ".join(k for k in INVENTED if k != "W_steer construction") + "."
    foot = "\n".join(textwrap.wrap(inv, 165)) + "\nHOLDOUT = held-out start timings + noise seeds on the same level (1-1), not held-out levels. Assisted, disclosed run."
    fig.text(0.01, 0.01, foot, fontsize=6.5, color="#444", va="bottom")
    fig.subplots_adjust(left=0.25, right=0.98, top=0.92, bottom=0.2)
    fig.savefig(CLIPS / "07_results_card.png")


def card_only():
    fe, dk = fair()
    card(fe, dk)


def numbers(fe, dk, n6):
    p = CLIPS / "numbers.md"
    t = p.read_text(encoding="utf-8")
    t = t.split("\n## clip 07")[0].split("\n" + MARK)[0]
    i6 = t.index("## clip 06")
    t = t[:i6] + ("## clip 06  (source: clips/data/shuffle_median_log.csv, runs/007_fair_eval.json) -- Part 6b replacement\n\n"
                  "| quantity | value |\n|---|---|\n" + "\n".join(f"| {q} | {v} |" for q, v in n6) + "\n")
    t += "\n## clip 07  (clips/07_results_card.png; source: runs/007_fair_eval.json, runs/007_default_knobs.json)\n\n"
    t += "| arm | HOLDOUT mean max_x | distinct trajectories of 10 | looming escapes | blind presses |\n|---|---|---|---|---|\n"
    for k in ("real/evolved_best", "real/4b_original", "shuf0_rn/evolved_best", "shuf1_rn/evolved_best", "shuf2_rn/evolved_best",
              "timer_evolved", "theta_rule_evolved"):
        d = fe[k]
        t += f"| {k} | {d['mean_max_x']:.0f} | {d['n_traj']} | {d.get('escapes_looming', '-')} | {d['blind_presses']:.1f} |\n"
    t += ("\nHOLDOUT = 5 start timings x sigma {0, 0.05} on level 1-1: held-out start timings, not held-out levels. Part 5 and earlier HOLDOUT "
          "means count 10 episodes but fewer distinct trajectories: real 4b fly 2 distinct (max_x 2754 x8, 1421 x2); Part 4 hopper at "
          "sigma 0: 1 distinct (3161 x5); default-knob real: 1 (723 x10).\n")
    t += (f"\n{MARK}\n\nNothing below is read off the connectome (source of truth: `knobs.INVENTED`). evolved = searched by CMA-ES on TRAIN; "
          "fixed = set by hand.\n\n| piece | how set | what it is |\n|---|---|---|\n")
    for k, (how, what) in INVENTED.items():
        t += f"| {k} | INVENTED ({how}) | {what} |\n"
    t += "\nWhat IS connectome: the 636-neuron cast and its synapse counts (MaleCNS v1.0); signs come from predicted neurotransmitter.\n"
    t += "\n## Checksums (sha256)\n\n| file | sha256 |\n|---|---|\n"
    files = ([CACHE / "W_steer.npy", CACHE / "W_steer_shuf0.npy"] + [CACHE / f"W_steer_shuf{i}_rn.npy" for i in range(5)]
             + [CACHE / "steer_bodies.parquet", CACHE / "steer_edges.parquet", CLIPS / "soma_xyz.npz"])
    for f in files:
        t += f"| {f.name} | {sha(f)} |\n"
    p.write_text(t, encoding="utf-8")


def main():
    fe, dk = fair()
    n6 = clip06(fe)
    card(fe, dk)
    numbers(fe, dk, n6)
    print("done")


if __name__ == "__main__":
    main()
