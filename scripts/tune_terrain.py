"""
tune_terrain.py — SPEC_terrain.md's lighter gain checks for the two new
circuits this sprint (takeoff: DNp01->GFC1-4->DLMn, and speed: DNp09),
same bar as tune_steering.py: spectral radius at a few g, plus a
constant/pulsed-drive settling check. Not a full Diagnostic-4 sweep.

    .venv/Scripts/python.exe -m scripts.tune_terrain
"""
from __future__ import annotations

import numpy as np

from fly.connectome import circuit
from fly.network import dynamics
from fly.circuits.load_takeoff_cached import load as load_takeoff
from fly.circuits.load_speed_cached import load as load_speed


def tune_takeoff():
    print("=" * 70)
    print("TAKEOFF CIRCUIT (DNp01 -> GFC1-4 -> DLMn)")
    print("=" * 70)
    bodies, edges, total_input, signs, W, order, diag = load_takeoff()
    K = W.shape[0]
    dnp01_mask = (bodies["type"] == "DNp01").to_numpy()
    dlmn_mask = bodies["type"].isin(["DLMn c-f", "DLMn a, b"]).to_numpy()

    print("spectral radius of W_takeoff at several g:")
    for g in (0.5, 0.7, 0.8, 0.9, 1.0):
        print(f"  g={g:<5} rho={circuit.spectral_radius(W, g):.4f}")

    print("\nDNp01-pulse settling check (a brief pulse on DNp01's rows, "
          "mimicking a real spike read from the jump circuit's HybridState, "
          "then nothing -- does DLMn recruitment rise and then decay, or "
          "does it ring/runaway?):")
    for g in (0.6, 0.7, 0.8, 0.9):
        h = np.zeros(K)
        I = np.zeros(K)
        dlmn_trace = []
        for t in range(200):
            I[:] = 0.0
            if t < 5:
                I[dnp01_mask] = 50.0  # one HybridState spike_amp-sized pulse
            h = dynamics.step(h, W, g, I)
            dlmn_trace.append(h[dlmn_mask].mean())
        dlmn_trace = np.array(dlmn_trace)
        peak = dlmn_trace.max()
        peak_t = int(dlmn_trace.argmax())
        tail = dlmn_trace[-20:].mean()
        clipped_frac = (dlmn_trace >= dynamics.CLIP - 1e-6).mean()
        print(f"  g={g:<4} DLMn peak={peak:.3f} @t={peak_t:3d}  "
              f"tail(last20) mean={tail:.4f}  clipped_frac={clipped_frac:.3f}")

    print("\nDecision: rho(g=1)=0.9998 -- this tight 46-neuron relay sits "
          "almost exactly AT the linear stability boundary, unlike the "
          "steering/speed circuits. g=0.8 keeps real headroom under it "
          "while the pulse check above shows DLMn actually rising in "
          "response to a DNp01 spike and decaying back down afterward, not "
          "ringing or pinning. -> G_TAKEOFF = 0.8")


def tune_speed():
    print()
    print("=" * 70)
    print("SPEED CIRCUIT (DNp09)")
    print("=" * 70)
    bodies, edges, total_input, signs, W, order, diag = load_speed()
    K = W.shape[0]
    dnp09_mask = (bodies["type"] == "DNp09").to_numpy()

    print("spectral radius of W_speed at several g:")
    for g in (0.5, 1.0, 1.2, 1.5, 2.0):
        print(f"  g={g:<5} rho={circuit.spectral_radius(W, g):.4f}")

    print("\nconstant-bias settling check (WALK_DRIVE on DNp09 only, "
          "400 steps, no other input):")
    for walk_drive in (1.0,):
        for g in (1.0, 1.2, 1.5):
            h = np.zeros(K)
            I = np.zeros(K)
            I[dnp09_mask] = walk_drive
            trace = []
            for _ in range(400):
                h = dynamics.step(h, W, g, I)
                trace.append(h[dnp09_mask].mean())
            trace = np.array(trace)
            tail = trace[-50:]
            clipped_frac = (trace >= dynamics.CLIP - 1e-6).mean()
            print(f"  WALK_DRIVE={walk_drive} g={g:<4} final mean={tail.mean():.3f} "
                  f"(std last50={tail.std():.4f}, clipped_frac={clipped_frac:.3f})")

    print("\nDecision: rho(g=1)=0.8275, comfortably sub-critical even at "
          "g=1.5. Pick g=1.2 (matches G_STEER, no reason for these two "
          "small threshold-expansion circuits to run at different gains) "
          "-> G_SPEED = 1.2. WALK_DRIVE=1.0 settles cleanly, no clipping "
          "-> WALK_DRIVE = 1.0. DNP09_SPEED_THRESHOLD set relative to that "
          "settled value in run_steering.py once the suppression term "
          "(active during jump/stall) is wired in -- see there for the "
          "final chosen number.")


if __name__ == "__main__":
    tune_takeoff()
    tune_speed()
