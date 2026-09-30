# What this file does, in plain English:
# Command-line version of the standard evaluation: runs a project's fly on held-out
# seeds with the real connectome and with a shuffled one and prints win rates with
# 95% confidence intervals (see tool/core/evaluation.py).
"""scripts/eval_connectome.py <project> [--n 20] [--seed0 1000] [--workers 4] [--max-frames N]

    .venv/Scripts/python.exe -m scripts.eval_connectome honest_1 --workers 10
"""

from __future__ import annotations

import argparse

from tool.core.evaluation import DEFAULT_N, DEFAULT_SEED0, format_eval, run_eval
from tool.core.project import ToolProject


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--seed0", type=int, default=DEFAULT_SEED0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=None)
    args = ap.parse_args()
    result = run_eval(ToolProject.open(args.project), n=args.n, seed0=args.seed0, workers=args.workers,
                      max_frames=args.max_frames)
    print(format_eval(result))


if __name__ == "__main__":
    main()
