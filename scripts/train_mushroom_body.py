# What this file does, in plain English:
# Command-line way to train the fly's mushroom body (learning centre). It is
# only a thin wrapper: the real work, and the recording of every episode in
# the tool's run store, is tool/core/training.py -- the same code the tool's
# Train button runs. It refuses to train into the read-only "legacy" project.
"""
train_mushroom_body.py -- SPEC_mushroom_body.md section 6, now through the
tool's run store (CLAUDE.md: headless scripts never bypass it).

    .venv/Scripts/python.exe -m scripts.train_mushroom_body <project> [episodes] \
        [--frame-cap 3000] [--shuffled N] [--checkpoint real_ep050.npy]
"""
import argparse
import sys

sys.path.insert(0, ".")

if __name__ == "__main__":
    import setuptools  # noqa: F401 -- must precede gym
    from tool.core.project import ToolProject
    from tool.core.tool_settings import TrainingSettings
    from tool.core.training import run_training

    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("episodes", type=int, nargs="?", default=200)
    ap.add_argument("--frame-cap", type=int, default=3000)
    ap.add_argument("--shuffled", type=int, default=0, help="number of shuffled control networks")
    ap.add_argument("--learning-rate", type=float, default=None)
    ap.add_argument("--event-proximal", action="store_true")
    ap.add_argument("--checkpoint", default=None)
    a = ap.parse_args()
    settings = TrainingSettings(episodes=a.episodes, frame_cap=a.frame_cap,
                                learning_rate=a.learning_rate, event_proximal=a.event_proximal,
                                include_shuffled=a.shuffled > 0, n_shuffled=max(a.shuffled, 1),
                                checkpoint=a.checkpoint)

    def emit(kind, payload):
        if kind == "episode":
            print(f"{payload['network']:>12} ep {payload['episode']:4d}  max_x={payload['max_x']:5d}"
                  f"  (run #{payload['number']})", flush=True)

    print(run_training(ToolProject.open(a.project), settings, emit=emit))
