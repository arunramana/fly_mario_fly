"""
run_mario.py -- wire the connectome-derived escape circuit to SMB 1-1 and
record video. Must run under fly_mario/.venv (numpy<2, gym==0.23.1 pins;
see requirements.txt / SPEC section 6).

Population dynamics: SPEC section 3, over the expanded ~1255-neuron
subgraph from section 1b. DNp01 spiking fallback (SPEC 1b sweep found no g
gives a stable-and-sharp band -- see README): DNp01 is a leaky
integrate-and-fire unit, everyone else is the plain ReLU rate model.

Three hand-set scalars total, all logged below and in the README:
  g                    -- global recurrent gain
  dnp01_spike_threshold -- DNp01 membrane potential to fire (the fallback)
  ttmn_press_threshold  -- TTMn activation to press A

    fly_mario/.venv/Scripts/python.exe run_mario.py
"""

from __future__ import annotations

import sys
import time

import setuptools  # noqa: F401  -- must import before gym on py3.12 (distutils shim)
import numpy as np
import cv2
import gym_super_mario_bros
from nes_py.wrappers import JoypadSpace

import dynamics
from load_cached import load

# ---- hand-set scalars -------------------------------------------------
# G was 3.5 -- passed the single-ramp diagnostics in tune.py but failed
# Diagnostic 4 (diag4.py, SPEC section 3): under sustained bilateral input
# the network never returned to baseline and pinned at the clip ceiling,
# so the 9 jumps in the first recorded video were not caused by looming.
# g=2.0 is the middle of the band [1.12, 3.35] that passes Diagnostic 4
# (checked robust across 5 random trace seeds) -- see diag4.py.
G = 2.0
DNP01_SPIKE_THRESHOLD = 0.5
TTMN_PRESS_THRESHOLD = 3.0
SPIKE_AMP = 50.0
# ---- mechanical output-interface parameters (not part of the neural
# model -- how long to hold the button once the decision is made) -------
JUMP_HOLD_FRAMES = 25
JUMP_COOLDOWN_FRAMES = 40

W_TILE = 16.0
MAX_FRAMES = 300

# RAM addresses, SPEC section 2
ADDR_MARIO_X = 0x0086
ADDR_MARIO_PAGE = 0x006D
ADDR_ENEMY_X = 0x0087
ADDR_ENEMY_ACTIVE = 0x000F
ADDR_ENEMY_TYPE = 0x0016
N_ENEMY_SLOTS = 5

# Powerups (mushroom/flower/star/1-up) share the same 5 enemy-object slots
# as actual enemies (SPEC_odour.md section 1) -- they are approach targets,
# not threats, and must never reach the looming detectors. Bug found via
# SPEC_habituation.md's investigation: run_steering.py's synthetic mushroom
# injection (a static object, never removed) was being read by this
# function as a permanent, unresolvable "enemy" once Mario ended up parked
# near it -- a real Goomba eventually gets walked past or jumped over,
# changing d and letting theta decay; a static injected object never does.
POWERUP_ID = 0x2E

MOVES = [["right", "B"], ["right", "A", "B"]]
RUN, JUMP = 0, 1


def enemy_thetas(ram, mario_x, prev_theta):
    """Nearest active THREAT's theta/dtheta per hemisphere. Enemies ahead of
    Mario (on-screen x >= mario_x) route Right; behind route Left -- our
    convention, SPEC doesn't fix one since retinotopy is skipped (section 2).
    Powerup-type slots are skipped -- see POWERUP_ID's comment."""
    theta = {"L": 0.0, "R": 0.0}
    d_out = {"L": None, "R": None}
    for i in range(N_ENEMY_SLOTS):
        if ram[ADDR_ENEMY_ACTIVE + i] == 0:
            continue
        if ram[ADDR_ENEMY_TYPE + i] == POWERUP_ID:
            continue
        enemy_x = int(ram[ADDR_ENEMY_X + i])
        d = enemy_x - int(mario_x)
        side = "R" if d >= 0 else "L"
        ad = max(abs(d), 1)
        th = 2.0 * np.arctan(W_TILE / (2.0 * ad))
        if th > theta[side]:
            theta[side] = th
            d_out[side] = d
    dtheta = {s: theta[s] - prev_theta[s] for s in ("L", "R")}
    return theta, dtheta, d_out


def make_env():
    env = gym_super_mario_bros.make("SuperMarioBros-1-1-v0")
    env = JoypadSpace(env, MOVES)
    return env


UPSCALE = 3
PANEL_H = 190


def draw_overlay(frame_bgr, info: dict, panel_h=PANEL_H, scale=UPSCALE):
    frame_bgr = cv2.resize(frame_bgr, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_NEAREST)
    h, w = frame_bgr.shape[:2]
    canvas = np.zeros((h + panel_h, w, 3), dtype=np.uint8)
    canvas[:h] = frame_bgr
    panel = canvas[h:]
    panel[:] = (24, 24, 24)

    fs = 0.62
    lines = [
        f"frame {info['frame']:5d}    side driven: {info['side']}",
        f"d_px={info['d_px']}   theta={info['theta']:.3f}   dtheta={info['dtheta']:+.3f}",
        f"LC4_mean={info['LC4_mean']:.3f}    LPLC2_mean={info['LPLC2_mean']:.3f}",
        f"DNp01[{info['side']}] mem={info['dnp01_mem']:.3f} "
        f"({'SPIKE' if info['dnp01_spike'] else '-'})    TTMn={info['ttmn']:.3f}",
        f"g={G}   DNp01_spike_th={DNP01_SPIKE_THRESHOLD}   TTMn_press_th={TTMN_PRESS_THRESHOLD}",
    ]
    y = 30
    for line in lines:
        cv2.putText(panel, line, (14, y), cv2.FONT_HERSHEY_SIMPLEX, fs,
                    (220, 220, 220), 1, cv2.LINE_AA)
        y += 30

    a_color = (0, 255, 0) if info["A"] else (70, 70, 70)
    cv2.rectangle(panel, (w - 110, 20), (w - 30, 90), a_color, -1)
    cv2.putText(panel, "A", (w - 84, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                (0, 0, 0), 3, cv2.LINE_AA)
    if info["A"]:
        cv2.putText(canvas, "JUMP!", (w // 2 - 90, 50), cv2.FONT_HERSHEY_SIMPLEX,
                    1.6, (0, 255, 0), 4, cv2.LINE_AA)
    return canvas


def main(out_path="mario_jump.mp4"):
    print("Loading connectome circuit (cached, expanded N=60)...")
    bodies, edges, total_input, signs, W, order, diag = load(N=60)
    K = W.shape[0]
    msk_all = {
        "LC4_L": ((bodies["type"] == "LC4") & (bodies["somaSide"] == "L")).to_numpy(),
        "LC4_R": ((bodies["type"] == "LC4") & (bodies["somaSide"] == "R")).to_numpy(),
        "LPLC2_L": ((bodies["type"] == "LPLC2") & (bodies["somaSide"] == "L")).to_numpy(),
        "LPLC2_R": ((bodies["type"] == "LPLC2") & (bodies["somaSide"] == "R")).to_numpy(),
        "DNp01_L": ((bodies["type"] == "DNp01") & (bodies["somaSide"] == "L")).to_numpy(),
        "DNp01_R": ((bodies["type"] == "DNp01") & (bodies["somaSide"] == "R")).to_numpy(),
        "TTMn_L": ((bodies["type"] == "TTMn") & (bodies["somaSide"] == "L")).to_numpy(),
        "TTMn_R": ((bodies["type"] == "TTMn") & (bodies["somaSide"] == "R")).to_numpy(),
        "LC4_all": (bodies["type"] == "LC4").to_numpy(),
        "LPLC2_all": (bodies["type"] == "LPLC2").to_numpy(),
    }
    dnp01_idx = np.where(msk_all["DNp01_L"] | msk_all["DNp01_R"])[0]  # [L, R] order? verify below
    # keep explicit L/R order for HybridState indexing
    dnp01_L_idx = np.where(msk_all["DNp01_L"])[0]
    dnp01_R_idx = np.where(msk_all["DNp01_R"])[0]
    dnp01_idx = np.concatenate([dnp01_L_idx, dnp01_R_idx])
    dnp01_pos = {"L": 0, "R": 1}  # position within dnp01_idx / st.mem

    st = dynamics.HybridState(K, dnp01_idx, spike_threshold=DNP01_SPIKE_THRESHOLD,
                               spike_amp=SPIKE_AMP)

    env = make_env()
    obs = env.reset()
    ram = env.unwrapped.ram

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = None

    prev_theta = {"L": 0.0, "R": 0.0}
    jump_hold = 0
    jump_cooldown = 0
    n_jumps = 0

    print("Running... (holding right+B, connectome decides when to press A)")
    for frame in range(MAX_FRAMES):
        mario_x = ram[ADDR_MARIO_X]
        theta, dtheta, d_out = enemy_thetas(ram, mario_x, prev_theta)
        prev_theta = theta

        I = np.zeros(K)
        I[msk_all["LC4_L"]] = abs(dtheta["L"])
        I[msk_all["LPLC2_L"]] = theta["L"]
        I[msk_all["LC4_R"]] = abs(dtheta["R"])
        I[msk_all["LPLC2_R"]] = theta["R"]

        for _ in range(dynamics.SUBSTEPS):
            h = st.step(W, G, I)

        ttmn_L = h[msk_all["TTMn_L"]].mean()
        ttmn_R = h[msk_all["TTMn_R"]].mean()
        ttmn_val = max(ttmn_L, ttmn_R)
        side = "R" if theta["R"] >= theta["L"] else "L"

        press = False
        if jump_cooldown > 0:
            jump_cooldown -= 1
        elif jump_hold == 0 and ttmn_val >= TTMN_PRESS_THRESHOLD:
            jump_hold = JUMP_HOLD_FRAMES
            n_jumps += 1
            print(f"  frame {frame}: TTMn={ttmn_val:.2f} >= {TTMN_PRESS_THRESHOLD} -> JUMP #{n_jumps} "
                  f"(d={d_out[side]}, theta={theta[side]:.3f})")

        if jump_hold > 0:
            action = JUMP
            press = True
            jump_hold -= 1
            if jump_hold == 0:
                jump_cooldown = JUMP_COOLDOWN_FRAMES
        else:
            action = RUN

        obs, reward, done, info_env = env.step(action)

        frame_bgr = cv2.cvtColor(obs, cv2.COLOR_RGB2BGR)
        info = {
            "frame": frame, "side": side,
            "d_px": d_out[side] if d_out[side] is not None else "-",
            "theta": theta[side], "dtheta": dtheta[side],
            "LC4_mean": h[msk_all["LC4_all"]].mean(),
            "LPLC2_mean": h[msk_all["LPLC2_all"]].mean(),
            "dnp01_mem": st.mem[dnp01_pos[side]],
            "dnp01_spike": bool(st.just_spiked[dnp01_pos[side]]),
            "ttmn": ttmn_val, "A": press,
        }
        canvas = draw_overlay(frame_bgr, info)

        if writer is None:
            h_c, w_c = canvas.shape[:2]
            writer = cv2.VideoWriter(out_path, fourcc, 60.0, (w_c, h_c))
        writer.write(canvas)

        if done:
            print(f"  episode ended at frame {frame} (death/flag)")
            break

    writer.release()
    env.close()
    print(f"\nSaved video -> {out_path}  ({frame+1} frames, {n_jumps} jump(s) triggered)")
    return n_jumps


if __name__ == "__main__":
    main()
