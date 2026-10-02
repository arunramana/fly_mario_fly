# What this file does, in plain English:
# Command-line entry to the redesigned brain's standard evaluation: real vs
# degree-preserving shuffled connectome on seeds 2000-2019, scored as "past the
# first Goomba" in level 1-1 (see brain/evaluation.py).
"""scripts/eval_brain.py [--n 20] [--seed0 2000] [--workers 8] [--max-frames 1500] [--out result.json]

    .venv/Scripts/python.exe -m scripts.eval_brain --workers 8
"""

from brain.evaluation import main

if __name__ == "__main__":
    main()
