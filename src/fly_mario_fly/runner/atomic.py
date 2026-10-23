"""Atomic file writes and tolerant reads, for the files a job process and the API share (job.json, progress.json ...).

On Windows, replacing a file while another process has it open fails with PermissionError (WinError 32), and a reader can
catch a file at the moment it is swapped. So: `replace_retry` tries again briefly before giving up, writers use a temp name
of their own (two processes writing the same job.json never share one), and `read_json` retries a file that is locked or
half-written instead of reporting it missing. This is the one place that does it; evolve, render and the API use it.
"""
from __future__ import annotations

import itertools
import json
import os
import threading
import time
from pathlib import Path

TRIES = 40
DELAY = 0.05                 # seconds between tries (about two seconds in all)
_n = itertools.count()


def replace_retry(src, dst, tries: int = TRIES, delay: float = DELAY) -> None:
    """os.replace(src, dst), trying again on PermissionError (the other side has the file open for a moment)."""
    for i in range(tries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            time.sleep(delay)


def _tmp(path: Path) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.{next(_n)}.tmp")


def write_bytes(path, data: bytes) -> None:
    path = Path(path)
    tmp = _tmp(path)
    try:
        tmp.write_bytes(data)
        replace_retry(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path, data) -> None:
    write_bytes(path, json.dumps(data, indent=1).encode("utf-8"))


def read_json(path, tries: int = TRIES, delay: float = DELAY):
    """The file's JSON, or None if it does not exist. A file that is locked or half-written is read again a few times."""
    path = Path(path)
    for i in range(tries):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            if i == tries - 1:
                return None
            time.sleep(delay)
