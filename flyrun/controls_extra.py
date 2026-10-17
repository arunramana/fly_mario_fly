"""Part 5 diagnostics added after the HOLDOUT table showed the shuffle never reaches Goomba #1:
 (a) assisted loom test (scripted driver walks Mario to x 250, then the circuit takes over; diagnostic only,
     never inside fitness): does a real / shuffled brain jump at Goomba #1?
 (b) what the default shuffled run does on its own (buttons), and (c) silence check of the shuffle-evolved genome.
python -m flyrun.controls_extra -> runs/005_extra.json"""
import json
import os
from dataclasses import replace

import numpy as np

from .brain import load_brain
from .controls import RUNS, genomes
from .genome import BASE
from .run import run_episode


def loom_test(brain, knobs, takeover=250):
    s, df = run_episode(replace(knobs, SENSOR_NOISE=0.0), brain, takeover_x=takeover, record_h=True,
                        max_frames=700, stuck_frames=150)
    fly = df[df.driver == "fly"]
    a = fly[fly.a == 1]
    H, m = df.attrs["H"], brain.masks
    first = a.iloc[0] if len(a) else None
    near = fly[fly.stim_src == "goomba"]
    return dict(summary=s, takeover_frame=int(fly.frame.iloc[0]) if len(fly) else None,
                first_a_frame=None if first is None else int(first.frame),
                first_a_x=None if first is None else int(first.x),
                theta_deg_at_first_a=None if first is None else round(float(np.degrees(first.theta)), 1),
                d_at_first_a=None if first is None else float(first.stim_d),
                max_theta_deg_seen=round(float(np.degrees(near.theta.max())), 1) if len(near) else None,
                ttmn_peak=float(H[:, m["TTMn"]].mean(1).max()),
                lc4_peak=float(H[:, m["LC4_R"]].mean(1).max()), lplc2_peak=float(H[:, m["LPLC2_R"]].mean(1).max()),
                dnp09_peak=float(H[:, m["DNp09"]].mean(1).max()))


def main():
    gs = genomes()
    out = {}
    for tag, wfile in (("real", None), ("shuf", "W_steer_shuf0.npy")):
        if wfile:
            os.environ["FLYRUN_WFILE"] = wfile
        else:
            os.environ.pop("FLYRUN_WFILE", None)
        brain = load_brain()
        out[f"loom_assisted/{tag}/default_knobs"] = loom_test(brain, BASE)
        s, df = run_episode(replace(BASE, SENSOR_NOISE=0.0), brain, max_frames=400, stuck_frames=150, record_h=True)
        H, m = df.attrs["H"], brain.masks
        out[f"default_run/{tag}"] = dict(buttons=df.buttons.value_counts().to_dict(), summary=s,
                                         x_first_last=[int(df.x.iloc[0]), int(df.x.iloc[-1])],
                                         dnp09_mean=float(H[:, m["DNp09"]].mean()), dnp09_max=float(H[:, m["DNp09"]].mean(1).max()),
                                         steer_mean=float(df.steer.mean()))
        if tag == "shuf":
            k = gs["shuf_evolved"]
            s0, d0 = run_episode(replace(k, PIPE_SENSE=False, PIT_SENSE=False, SENSOR_NOISE=0.0), brain,
                                 enemy_input=False, max_frames=600, stuck_frames=10**6)
            out["silence_shuf_evolved"] = dict(a_frac=float(d0.a.mean()), ttmn_max=float(d0.ttmn.max()), x_end=int(d0.x.iloc[-1]))
            out["loom_assisted/shuf/shuf_evolved"] = loom_test(brain, k)
    os.environ.pop("FLYRUN_WFILE", None)
    (RUNS / "005_extra.json").write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
