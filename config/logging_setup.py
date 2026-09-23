# What this file does, in plain English:
# Sets up logging for a run. Everything the program reports goes to a new
# file in the logs/ folder (one file per run, named with the date and time),
# and only the short, important messages also appear on screen. Library code
# never calls this; the run scripts (or your own tool) call it once at start.
"""config/logging_setup.py -- one place to configure logging.

Library modules only do `log = logging.getLogger(__name__)`. An entry point
calls `setup_logging(run_name)` once; `run_steering.main()` and
`run_mario.main()` call `ensure_logging()`, which does nothing if a caller
(a tool, a script) has already configured it.

Console gets INFO and above, message text only. The file gets DEBUG and
above with timestamps and the logger name, including the circuit build
reports the cached loaders capture.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).parent.parent / "logs"

# Loggers below WARNING are kept only from these top-level names; third-party
# libraries (PIL logs every PNG chunk at DEBUG) are held to WARNING.
PROJECT_LOGGERS = {"fly", "mario", "bridge", "sim", "config", "render",
                   "scripts", "run_steering", "run_mario", "__main__"}


class _ProjectOnlyBelowWarning(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return (record.levelno >= logging.WARNING
                or record.name.split(".", 1)[0] in PROJECT_LOGGERS)


_handlers: list[logging.Handler] = []
_current_path: Path | None = None


def setup_logging(run_name: str = "run", console_level: int = logging.INFO,
                  file_level: int = logging.DEBUG,
                  logs_dir: Path | str | None = None) -> Path:
    """Start a new log file for `run_name` and return its path. Calling it
    again replaces this module's handlers (not anyone else's, e.g. pytest's)."""
    global _current_path
    root = logging.getLogger()
    for h in _handlers:
        root.removeHandler(h)
        h.close()
    _handlers.clear()

    out_dir = Path(logs_dir) if logs_dir is not None else LOGS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w.-]+", "_", run_name) or "run"
    path = out_dir / f"{datetime.now():%Y-%m-%d_%H%M%S}_{safe_name}.log"

    file_h = logging.FileHandler(path, encoding="utf-8")
    file_h.setLevel(file_level)
    file_h.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    console_h = logging.StreamHandler()
    console_h.setLevel(console_level)
    console_h.setFormatter(logging.Formatter("%(message)s"))

    for h in (file_h, console_h):
        h.addFilter(_ProjectOnlyBelowWarning())
        root.addHandler(h)
        _handlers.append(h)
    root.setLevel(min(console_level, file_level, root.level or logging.WARNING))
    _current_path = path
    return path


def ensure_logging(run_name: str = "run") -> Path:
    """setup_logging(run_name) unless it has already been called."""
    if _current_path is None:
        return setup_logging(run_name)
    return _current_path


def current_log_path() -> Path | None:
    return _current_path
