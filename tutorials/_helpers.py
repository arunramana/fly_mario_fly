"""Small helpers shared by the notebooks. Plotting and path checks only: all the real work calls the repo's own code."""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

warnings.filterwarnings("ignore")      # gym prints deprecation warnings that are not about this tutorial

TEAL, ORANGE = "#30d0c0", "#f8a010"    # the repo's honesty colours: teal = read off the connectome, orange = invented by us

NEEDED = ["connectome-weights-male-cns-v1.0-minconf-0.5.feather",
          "body-annotations-male-cns-v1.0-minconf-0.5.feather",
          "body-neurotransmitters-male-cns-v1.0.feather"]


def use_data_folder(path) -> Path:
    """Point the repo at your MaleCNS folder and check the three files are there. Never downloads anything.

    `path` is the folder that CONTAINS `malecns_v1.0/` (the same folder as $FLY_MARIO_FLY_DATA in the main README).
    """
    root = Path(path).expanduser()
    missing = [f for f in NEEDED if not (root / "malecns_v1.0" / f).exists()]
    if missing:
        raise FileNotFoundError(
            f"Could not find MaleCNS files in {root / 'malecns_v1.0'}:\n  " + "\n  ".join(missing) +
            "\nSee tutorials/README.md ('Getting the data') and set DATA_DIR in the first code cell.")
    os.environ["FLY_MARIO_FLY_DATA"] = str(root)
    return root


def show_frame(frame, ax=None, title=None, boxes=(), scroll=0, colour="red"):
    """Draw one 240x256 NES screen. `boxes` are (x, y, w, h) in LEVEL pixels (level y starts below the 32-px status bar, so 32 is added); `scroll` is the screen's left edge in the level."""
    ax = ax or plt.subplots(figsize=(5, 4.7))[1]
    ax.imshow(frame, interpolation="nearest")
    for x, y, w, h in boxes:
        ax.add_patch(Rectangle((x - scroll - 0.5, y + 32 - 0.5), w, h, fill=False, ec=colour, lw=1.5))
    ax.set_title(title or "", fontsize=9)
    ax.axis("off")
    return ax


def teal_orange_legend(ax):
    """A tiny legend for the honesty rule."""
    ax.plot([], [], "s", color=TEAL, label="real (from the connectome)")
    ax.plot([], [], "s", color=ORANGE, label="invented by us")
    ax.legend(loc="upper right", fontsize=8, frameon=False)
