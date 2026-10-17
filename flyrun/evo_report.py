"""Post-evolution checks 1-5 + curves + death maps. python -m flyrun.evo_report
Writes runs/003_report_numbers.json and runs/003_curve_<arm>.png (read by runs/003_evolution.md)."""
import json
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .brain import load_brain
from .fitness import WorkerPool, evaluate
from .genome import CONTROLLER, SPECS, decode
from .render_stage import EVO, replay
from .run import run_episode

RUNS = EVO.parent / "runs"
SEEDS = list(range(10))


def stats(res):
    xs = [p["max_x"] for p in res["per_seed"]]
    return dict(mean_max_x=float(np.mean(xs)), min_max_x=int(min(xs)), max_max_x=int(max(xs)),
                flag_rate=float(np.mean([p["flag_get"] for p in res["per_seed"]])),
                mean_fitness=res["mean_fitness"], max_x=xs,
                ends=[(p["end_reason"], p["x_at_end"], p["cause"]) for p in res["per_seed"]])


def obstacle_table(max_x):
    lm = pd.read_csv(RUNS / "001_level_map.csv")
    rows = []
    for _, o in lm.iterrows():
        end = o.x + (16 if o.kind == "wall" else o["size"])
        rows.append(dict(kind=o.kind, x=int(o.x), size=int(o["size"]), cleared=bool(max_x > end)))
    return rows


def main():
    brain = load_brain()
    out = {}
    with WorkerPool(12) as pool:
        for arm in ("fly", "theta"):
            g = pd.read_csv(EVO / arm / "gen.csv")
            best = json.loads((EVO / arm / "best_genome.json").read_text())
            u = np.array(best["u"])
            ctl = CONTROLLER[arm]
            a = dict(best=best, n_restarts=int(g.restart.nunique()), gens_per_restart=g.groupby("restart").gen.max().add(1).to_dict())
            # 1. gen 0 best >= default fitness (723)
            a["gen0_best"] = {int(r): float(v) for r, v in g[g.gen == 0].groupby("restart").gen_best_fit.max().items()}
            a["check1_gen0_ge_723"] = all(v >= 723 for v in a["gen0_best"].values())
            # 2. best_fit non-decreasing within each restart
            a["check2_nondecreasing"] = all(np.all(np.diff(d.sort_values("gen").best_fit.values) >= 0)
                                            for _, d in g.groupby("restart"))
            # 3. exact reproduction, alone
            s, df = replay(arm, u, record=False)
            fit = s["max_x"] + 10000 * int(s["flag_get"])
            a["replay"] = dict(summary=s, fitness=fit, logged=best["fitness"])
            a["check3_reproduces"] = bool(fit == best["fitness"])
            # death map of the best run
            a["obstacles"] = obstacle_table(s["max_x"])
            ev = df[(df.a == 1) & (df.a.shift(1, fill_value=0) == 0)]
            a["a_onsets"] = ev[["frame", "x", "stim_src", "stim_d"]].round(1).to_dict("records")
            iv = np.diff(ev.frame.values)
            far = ev[(ev.stim_d.isna()) | (ev.stim_d > 60)]
            a["behaviour"] = dict(A_frac=float(df.a.mean()), n_onsets=int(len(ev)),
                                  onset_interval_median=float(np.median(iv)) if len(iv) else None,
                                  onsets_no_or_far_stimulus=int(len(far)),
                                  ttmn_q05_q50_q95=df.ttmn.quantile([.05, .5, .95]).round(3).tolist())
            if arm == "fly":   # does it hop with nothing in view?
                k0, _ = decode(arm, u)
                s0, d0 = run_episode(replace(k0, PIPE_SENSE=False, PIT_SENSE=False), brain, enemy_input=False,
                                     max_frames=600, stuck_frames=10**6)
                a["behaviour"]["silence_600f"] = dict(A_frac=float(d0.a.mean()), max_x=s0["max_x"],
                                                      ttmn_max=float(d0.ttmn.max()))
            # 4. robustness of the best
            knobs, vals = decode(arm, u)
            rob = {}
            for sg in (0.05, 0.10):
                rob[f"sigma_{sg}"] = stats(evaluate(replace(knobs, SENSOR_NOISE=sg), brain, SEEDS, pool=pool, controller=ctl))
            for ns in (0, 7, 17, 33):
                r = evaluate(knobs, brain, [0], pool=pool, controller=ctl, noop_start=ns)
                rob[f"noop_{ns}"] = stats(r)
            a["robustness"] = rob
            # 5. knobs at a range bound (unit-space within 2% of an edge)
            a["bound_knobs"] = [dict(knob=n, value=vals[n], lo=lo, hi=hi, at="lo" if x < 0.02 else "hi")
                                for (n, lo, hi, _), x in zip(SPECS[arm], u) if x < 0.02 or x > 0.98]
            a["per_restart_best"] = {int(r): dict(fit=float(d.best_fit.max()), max_x=int(d.best_max_x.iloc[-1]),
                                                  end=d.best_end_reason.iloc[-1], cause=d.best_cause.iloc[-1],
                                                  gens=int(d.gen.max()) + 1,
                                                  genome=d.best_genome.iloc[-1])
                                     for r, d in g.groupby("restart")}
            # curve
            fig, ax = plt.subplots(figsize=(7, 3.8))
            for r, d in g.groupby("restart"):
                ax.plot(d.gen, d.best_fit, "-o", ms=3, label=f"best (restart {r})")
                ax.plot(d.gen, d.mean_fit, "--", alpha=0.6, label=f"population mean (restart {r})")
            ax.set_xlabel("generation")
            ax.set_ylabel("fitness (max_x + 10000 flag)")
            ax.set_title(f"{arm} arm")
            ax.legend(fontsize=6)
            fig.tight_layout()
            fig.savefig(RUNS / f"003_curve_{arm}.png", dpi=130)
            plt.close(fig)
            out[arm] = a
    timing = json.loads((EVO / "timing.json").read_text()) if (EVO / "timing.json").exists() else {}
    out["timing_s"] = timing
    (RUNS / "003_report_numbers.json").write_text(json.dumps(out, indent=2, default=str))
    for arm in ("fly", "theta"):
        a = out[arm]
        print(arm, "best", a["best"]["fitness"], a["best"]["genome"], "restart", a["best"]["restart"])
        print("  checks", a["check1_gen0_ge_723"], a["check2_nondecreasing"], a["check3_reproduces"], "bounds", a["bound_knobs"])
        print("  replay", a["replay"]["summary"])
        for k, v in a["robustness"].items():
            print("  ", k, round(v["mean_max_x"], 1), v["min_max_x"], v["flag_rate"])


if __name__ == "__main__":
    main()
