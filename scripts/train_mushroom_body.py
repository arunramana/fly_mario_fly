"""
train_mushroom_body.py -- SPEC_mushroom_body.md section 6: 500 episodes
from an identical savestate, x-progress per episode as the learning curve.
headless, frame_skip=1 (013's own finding: frame_skip changes behaviour
chaotically -- not used for training here).

    .venv/Scripts/python.exe -m scripts.train_mushroom_body [n_episodes]
"""
import sys
sys.path.insert(0, ".")
import csv
import time

import run_steering as rs

N_EPISODES = int(sys.argv[1]) if len(sys.argv) > 1 else 500
LEVEL = "1-1"
MAX_FRAMES = 1200
WARMUP_FRAMES = 60

if __name__ == "__main__":
    env = rs.make_env(LEVEL)
    mb_weights = None
    rows = []
    t_start = time.time()
    with open("projects/legacy/telemetry/mb_training_curve.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["episode", "max_x_abs", "n_frames", "died", "n_escape_jumps",
                          "n_dnp01_fired", "n_dnp02_fired", "wall_s"])
        for ep in range(N_EPISODES):
            t0 = time.time()
            tel, info = rs.main(
                out_mp4="IGNORED", level=LEVEL, max_frames=MAX_FRAMES,
                record_video=False, frame_skip=1,
                savestate={"env": env, "warmup_frames": WARMUP_FRAMES},
                mb_weights=mb_weights,
            )
            mb_weights = info["mb_weights"]
            dt = time.time() - t0
            row = [ep, info["max_x_abs"], info["n_frames"], info["died_or_flagged"],
                   info["n_escape_jumps"], info["n_dnp01_fired"], info["n_dnp02_fired"], dt]
            writer.writerow(row)
            f.flush()
            rows.append(row)
            if ep % 25 == 0 or ep == N_EPISODES - 1:
                recent = [r[1] for r in rows[-25:]]
                print(f"episode {ep:4d}: max_x={info['max_x_abs']:5d} "
                      f"frames={info['n_frames']:4d} died={info['died_or_flagged']} "
                      f"(recent-25 mean max_x={sum(recent)/len(recent):.1f}) "
                      f"[{dt:.2f}s/ep, {time.time()-t_start:.0f}s total]", flush=True)
    env.close()
    import numpy as np
    np.save("projects/legacy/telemetry/mb_trained_weights.npy", mb_weights)
    print(f"\nDone: {N_EPISODES} episodes in {time.time()-t_start:.1f}s. "
          f"Saved projects/legacy/telemetry/mb_training_curve.csv and mb_trained_weights.npy")
