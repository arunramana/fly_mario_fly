# What this file does, in plain English:
# Command-line entry to experiment E1 (jump the Goomba): real vs shuffled
# connectome on seeds 3000-3019 (see brain/e1.py).
"""scripts/eval_e1.py [--n 20] [--seed0 3000] [--workers 8] [--out result.json]

    .venv/Scripts/python.exe -m scripts.eval_e1 --workers 8
"""

from brain.e1 import main

if __name__ == "__main__":
    main()
