"""Finished videos on disk, bounded by bytes. `<key>.mp4` and `<key>.json` (the run's summary) per entry; the least recently
used entry goes first. Entries are written under a temporary name and renamed, so a reader never sees half a file."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path


class DiskCache:
    def __init__(self, folder: Path, max_bytes: int):
        self.dir, self.max_bytes = Path(folder), int(max_bytes)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        for p in self.dir.glob("*.part*"):               # a crash mid-write leaves these; nothing else may
            p.unlink(missing_ok=True)

    def mp4(self, key: str) -> Path:
        return self.dir / f"{key}.mp4"

    def tmp(self, key: str) -> Path:
        return self.dir / f"{key}.part.mp4"

    def get(self, key: str):
        """The summary dict of a cached run (and mark it used), or None."""
        with self.lock:
            j, v = self.dir / f"{key}.json", self.mp4(key)
            if not (j.exists() and v.exists()):
                return None
            os.utime(j), os.utime(v)
            return json.loads(j.read_text(encoding="utf-8"))

    def put(self, key: str, summary: dict) -> None:
        """Adopt the finished tmp(key) file as the entry for `key`, then trim to the byte limit."""
        with self.lock:
            part = self.dir / f"{key}.part.json"
            part.write_text(json.dumps(summary), encoding="utf-8")
            os.replace(self.tmp(key), self.mp4(key))
            os.replace(part, self.dir / f"{key}.json")
            self._trim(keep=key)

    def size(self) -> int:
        return sum(p.stat().st_size for p in self.dir.iterdir() if p.is_file())

    def keys(self) -> list:
        return sorted(p.stem for p in self.dir.glob("*.mp4") if not p.name.endswith(".part.mp4"))

    def _trim(self, keep: str) -> None:
        entries = sorted((p for p in self.dir.glob("*.mp4") if not p.name.endswith(".part.mp4") and p.stem != keep),
                         key=lambda p: p.stat().st_mtime)
        total = self.size()
        while total > self.max_bytes and entries:
            v = entries.pop(0)
            for p in (v, v.with_suffix(".json")):
                if p.exists():
                    total -= p.stat().st_size
                    p.unlink()
