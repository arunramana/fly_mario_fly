"""
adapt_sweep.py -- SPEC_jump.md section 3 task: "check whether a leak/
adaptation term is the missing piece."

Grid-searches (g, alpha_a, beta) for dynamics.AdaptiveHybridState against
Diagnostic 4 (diag4.py). Plain g alone (diag4.py --sweep) is checked first;
this is only worth running if that sweep comes back empty, since adaptation
should not be adopted if a bare gain change already fixes it (SPEC's
two-scalar budget, CLAUDE.md invariant 3).

    .venv/Scripts/python.exe -m scripts.adapt_sweep
"""
from __future__ import annotations

from fly.network import dynamics
from scripts.diag4 import diagnostic4
from fly.connectome.load_cached import load

G_VALUES = [0.3, 0.5, 0.7, 0.9, 1.0, 1.1, 1.3, 1.5, 2.0, 3.5]
ALPHA_A_VALUES = [0.005, 0.02, 0.05]   # slow vs. the leak's alpha=0.3
BETA_VALUES = [1.0, 3.0, 8.0]

SPIKE_THRESHOLD = 0.5
SPIKE_AMP = 50.0
TTMN_THRESHOLD = 3.0


def make_state_factory(alpha_a, beta):
    def make_state(K, dnp01_idx, spike_threshold, spike_amp):
        return dynamics.AdaptiveHybridState(K, dnp01_idx, spike_threshold,
                                             alpha_a, beta, spike_amp)
    return make_state


if __name__ == "__main__":
    print("Loading the expanded N=60 circuit (cached)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)

    winners = []
    for alpha_a in ALPHA_A_VALUES:
        for beta in BETA_VALUES:
            make_state = make_state_factory(alpha_a, beta)
            for g in G_VALUES:
                r = diagnostic4(W, bodies, g, SPIKE_THRESHOLD, SPIKE_AMP,
                                 TTMN_THRESHOLD, verbose=False, make_state=make_state)
                tag = "PASS" if r["pass"] else "fail"
                print(f"  alpha_a={alpha_a:<6} beta={beta:<5} g={g:<5} "
                      f"c1={'P' if r['c1']['pass'] else 'F'} "
                      f"c2={'P' if r['c2']['pass'] else 'F'} "
                      f"c3={'P' if r['c3']['pass'] else 'F'} "
                      f"c4={'P' if r['c4']['pass'] else 'F'}  {tag}")
                if r["pass"]:
                    winners.append((alpha_a, beta, g))

    print("\n=== Summary ===")
    if winners:
        print(f"{len(winners)} (alpha_a, beta, g) combinations pass all four Diagnostic 4 checks:")
        for w in winners:
            print(f"  alpha_a={w[0]} beta={w[1]} g={w[2]}")
    else:
        print("No (alpha_a, beta, g) combination in this grid passes Diagnostic 4. "
              "Adaptation alone (over this grid) is not the fix.")
