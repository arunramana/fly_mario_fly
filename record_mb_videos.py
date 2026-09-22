"""Record the before (untrained) and after (trained) mushroom-body videos,
same savestate for both. Run after train_mushroom_body.py has produced
mb_trained_weights.npy."""
import sys
sys.path.insert(0, ".")
import numpy as np
import run_steering as rs

LEVEL = "1-1"
MAX_FRAMES = 1200
WARMUP_FRAMES = 60

if __name__ == "__main__":
    print("=== BEFORE (untrained) ===")
    tel_before, info_before = rs.main(
        out_mp4="runs/014a_before.mp4", level=LEVEL, max_frames=MAX_FRAMES,
        record_video=True, frame_skip=1,
        savestate={"env": rs.make_env(LEVEL), "warmup_frames": WARMUP_FRAMES},
        mb_weights=None,
    )
    print(info_before)

    trained = np.load("mb_trained_weights.npy")
    print("\n=== AFTER (trained,", trained.shape, ") ===")
    tel_after, info_after = rs.main(
        out_mp4="runs/014b_after.mp4", level=LEVEL, max_frames=MAX_FRAMES,
        record_video=True, frame_skip=1,
        savestate={"env": rs.make_env(LEVEL), "warmup_frames": WARMUP_FRAMES},
        mb_weights=trained,
    )
    print(info_after)
