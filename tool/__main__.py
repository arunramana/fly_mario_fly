"""python -m tool -- launches the GUI (tool/PLAN.md P3).

multiprocessing.freeze_support() and the __main__ guard matter here: Play
(main_window.py) spawns a worker process with the "spawn" start method,
which re-imports this module in the child -- without the guard, the
child would try to open a second GUI instead of just running the worker
function it was given.
"""
from __future__ import annotations

import multiprocessing as mp
import sys


def _main() -> int:
    from tool.ui.app import main
    return main()


if __name__ == "__main__":
    mp.freeze_support()
    sys.exit(_main())
