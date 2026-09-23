# What this file does, in plain English:
# Makes 20 "shuffled" copies of the jump circuit (same neurons, wiring
# scrambled at random). For the real circuit and each copy, it searches for
# an overall connection strength g that passes diag4.py's stress test: a
# quick shortened test first, then the full test to confirm. Saves the
# results to projects/legacy/telemetry/shuffle_sweep_results.json.
"""
shuffle_sweep.py -- SPEC section 5, done properly: n=20 shuffles, each tuned
with the SAME Diagnostic-4 procedure the real circuit got. Matched
procedure, not matched parameter -- g=2.0 was selected FOR the real
circuit; handing it to a shuffle would compare a tuned network to an
untuned one, which answers nothing about the wiring.

Profiled: a single full Diagnostic-4 call (3000 frames x 10 substeps =
30,000 HybridState.step calls) costs ~20s even with BLAS pinned to one
thread (small-matrix BLAS threading overhead otherwise makes it ~110s --
run this, and everything downstream that loops over `dynamics.step`, with
OMP_NUM_THREADS=1). A naive 21-network x full-grid sweep is ~2.75h even
optimized. Two stages instead, same 4 checks and thresholds throughout,
only the trace LENGTH differs between stages:

  1. SCREEN every network across a coarse g grid with a shorter trace
     (2 bursts instead of 4 -- still both approach and quiet regions, just
     less of them; a faster, slightly weaker version of the same test).
  2. CONFIRM the smallest passing screen candidate against the FULL
     Diagnostic-4 trace (>=2000 frames, SPEC's literal minimum -- identical
     to what the real circuit was checked against). Try the next candidate
     if confirmation fails. A network with no confirmed g is reported as
     exactly that -- SPEC anticipated this as a valid, informative outcome.

    .venv/Scripts/python.exe -m scripts.shuffle_sweep
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import contextlib
import io
import json
import time

from fly.connectome import circuit
from scripts.diag4 import diagnostic4
from fly.connectome.load_cached import load

N_SHUFFLES = 20
SCREEN_GRID = [0.05, 0.1, 0.2, 0.4, 0.7, 1.0, 1.5, 2.0, 3.0, 4.5, 7.0, 11.0, 17.0, 25.0]
SPIKE_THRESHOLD = 0.5
SPIKE_AMP = 50.0
TTMN_THRESHOLD = 3.0


def screen(W, bodies):
    passing = []
    for g in SCREEN_GRID:
        r = diagnostic4(W, bodies, g, SPIKE_THRESHOLD, SPIKE_AMP, TTMN_THRESHOLD,
                         n_bursts=2, burst_frames=200, quiet_frames=100, verbose=False,
                         require_spec_minimum=False)
        if r["pass"]:
            passing.append(g)
    return passing


def confirm(W, bodies, candidates):
    for g in candidates:
        r = diagnostic4(W, bodies, g, SPIKE_THRESHOLD, SPIKE_AMP, TTMN_THRESHOLD, verbose=False)
        if r["pass"]:
            return g
    return None


def find_g(W, bodies, label):
    t0 = time.time()
    candidates = screen(W, bodies)
    chosen = confirm(W, bodies, candidates) if candidates else None
    dt = time.time() - t0
    print(f"{label}: screen candidates={candidates} -> confirmed g={chosen}  ({dt:.1f}s)", flush=True)
    return chosen, candidates


if __name__ == "__main__":
    print("Loading the expanded N=60 circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)

    results = {}
    g_real, cand_real = find_g(W, bodies, "REAL")
    results["real"] = {"g": g_real, "screen_candidates": cand_real,
                        "rho_g1": circuit.spectral_radius(W, 1.0)}

    for seed in range(N_SHUFFLES):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            W_s, order_s, diag_s = circuit.build_shuffled(bodies, edges, total_input, signs, seed=seed)
        assert (order == order_s).all()
        g_s, cand_s = find_g(W_s, bodies, f"shuffle{seed:02d}")
        results[f"shuffle{seed:02d}"] = {"g": g_s, "screen_candidates": cand_s,
                                          "rho_g1": circuit.spectral_radius(W_s, 1.0)}
        with open("projects/legacy/telemetry/shuffle_sweep_results.json", "w") as f:
            json.dump(results, f, indent=2)

    print("\nwrote projects/legacy/telemetry/shuffle_sweep_results.json")
    n_found = sum(1 for v in results.values() if v["g"] is not None) - (1 if results["real"]["g"] else 0)
    print(f"{n_found}/{N_SHUFFLES} shuffles found a confirmed g.")
