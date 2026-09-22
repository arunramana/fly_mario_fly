"""
rerun_battery_g2.py -- the battery again with A at g=2.0 instead of the
Diagnostic-4-screen's g=1.5.

The 2x2 (g in {1.5, 2.0} x warm-up on/off, level 1-1 seed 0, 4000 frames)
showed g=2.0 survives regardless of warm-up and g=1.5 dies regardless of
warm-up: the gain was the problem, not the seeded run-up. g=1.5 passing
Diagnostic 4 (synthetic sustained input) but losing immediately in live
play is a real gap between "stable and causal on a synthetic trace" and
"good at the actual game" -- worth a note in the README, not a reason to
distrust either result.

Also drops level 1-3: all three controllers died there at IDENTICAL frames
in the previous battery (regardless of controller), because it's pits, not
enemies -- a looming detector has nothing to say about a hole in the floor.
2 levels x 3 seeds x 3 controllers = 18 runs.

C is re-tuned against the new A (g=2.0) -- its whole point is matching A's
CURRENT jump rate, and A's behavior at g=2.0 is nothing like g=1.5. B is
unchanged (shuffle07, g=3.0, already the best of the confirmed 20).

    python rerun_battery_g2.py
"""
from __future__ import annotations

import json

import pandas as pd

from compare_controllers import (LEVELS, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD,
                                  battery, build_shuffled_quiet, make_baseline_decider,
                                  make_circuit_decider, record_hero_run, run_episode,
                                  tune_baseline_c)
from load_cached import load

G_A = 2.0
LEVELS_2 = ["1-1", "1-2"]

if __name__ == "__main__":
    print("Loading the expanded N=60 circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)

    with open("shuffle_sweep_results.json") as f:
        sweep = json.load(f)
    best_seed, g_best = 7, sweep["shuffle07"]["g"]
    assert g_best == 3.0, "shuffle07's confirmed g changed -- rebuild the sweep before trusting this"
    W_best, order_best, _ = build_shuffled_quiet(bodies, edges, total_input, signs, best_seed)
    assert (order == order_best).all()

    print(f"\nRe-tuning C's threshold c against A at g={G_A} (level 1-1, seed 0)...")
    log_a0 = run_episode(make_circuit_decider(W, bodies, G_A, DNP01_SPIKE_THRESHOLD,
                                               SPIKE_AMP, TTMN_PRESS_THRESHOLD))
    c_star, n_c, log_c0 = tune_baseline_c(log_a0["n_jumps"])
    print(f"A: survival={log_a0['n_frames']} jumps={log_a0['n_jumps']} "
          f"ended={'died/flagged' if log_a0['died_or_flagged'] else 'hit max_frames'}")
    print(f"c={c_star:.4f} -> C jumps={n_c} (target {log_a0['n_jumps']}), "
          f"survival={log_c0['n_frames']} "
          f"ended={'died/flagged' if log_c0['died_or_flagged'] else 'hit max_frames'}")

    controllers_spec = [
        ("A_real", f"g={G_A} (2x2-confirmed: survives with/without warm-up)", "real", None, G_A),
        (f"B_shuffle{best_seed:02d}", f"g={g_best} (best of 20 shuffles, confirmed Diagnostic-4)",
         "shuffle", best_seed, g_best),
        ("C_theta", f"c={c_star:.4f} (tuned to A's jump rate at g={G_A}, 1-1 seed 0)", "baseline", None, c_star),
    ]

    print(f"\n=== Battery: {LEVELS_2} x 3 seeds x 3 controllers (multiprocessing.Pool(8)) ===")
    rows = battery(controllers_spec, levels=LEVELS_2, seeds=(0, 1, 2), n_workers=8)
    df = pd.DataFrame(rows)
    df.to_csv("compare_controllers_battery_g2.csv", index=False)
    print("\nSaved compare_controllers_battery_g2.csv.")

    print("\n=== Recording hero runs (level 1-1, seed 0) for runs/005*.mp4 ===")
    record_hero_run(make_circuit_decider(W, bodies, G_A, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD),
                     "A", "runs/005a_real.mp4", level="1-1", seed=0,
                     caption=f"A: real connectome, g={G_A}")
    record_hero_run(make_circuit_decider(W_best, bodies, g_best, DNP01_SPIKE_THRESHOLD, SPIKE_AMP, TTMN_PRESS_THRESHOLD),
                     "B", "runs/005b_shuffled_best.mp4", level="1-1", seed=0,
                     caption=f"B: shuffled connectome (best of 20), g={g_best}")
    record_hero_run(make_baseline_decider(c_star), "C", "runs/005c_theta.mp4", level="1-1", seed=0,
                     caption=f"C: theta > c baseline, c={c_star:.4f}")
