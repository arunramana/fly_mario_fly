"""Brains as files in a folder: export every cached brain once, then run from that folder with no MaleCNS data and no building.

    export_brains(data_root, dest)   copy the cached brains of every mechanism set into `dest` (needs the data to have been built once)
    install(dest)                    make the runner load brains from `dest` (lazily, one file per mechanism set the first time it is used)

The lite server ships `dest` (a few tens of MB) instead of the 1 GB connectome. The weights are the same arrays, loaded with
`Brain.load`, so a run from `dest` is identical to a run from the data folder.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from fly_mario_fly.fly import brain as fb
from fly_mario_fly.runner import session

MANIFEST = "manifest.json"


def spec_key(spec) -> str:
    return fb.brain_name(spec)         # the same name the full tool caches under, without the data hash: specs that differ only in
                                       # mechanisms that add no neurons (escape, walking) share one brain


def export_brains(data_root: Path, dest: Path) -> dict:
    """Copy each cached brain npz of `fb.all_specs()` into `dest`; write manifest.json {key: {file, sha256, neurons}}."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for spec in fb.all_specs():
        src = fb.brain_path(spec, Path(data_root))
        if not src.exists():
            raise FileNotFoundError(f"{src} is missing: build the brains first (python scripts/download_data.py --build-brains)")
        name = f"{spec_key(spec)}.npz"
        shutil.copyfile(src, dest / name)
        manifest[spec_key(spec)] = {"file": name, "sha256": hashlib.sha256((dest / name).read_bytes()).hexdigest(),
                                    "bytes": (dest / name).stat().st_size}
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def install(dest: Path, keep: int = 8) -> dict:
    """Make `runner.get_brain` load from `dest`. Returns the manifest. A brain that is not in it is an error, never a build.
    At most `keep` brains stay in memory: loading one more drops the one loaded longest ago (it is reloaded from its file if needed)."""
    dest = Path(dest)
    manifest = json.loads((dest / MANIFEST).read_text(encoding="utf-8"))

    def load(spec):
        entry = manifest.get(spec_key(spec))
        if entry is None:
            raise KeyError(f"no brain for {spec_key(spec)!r} in {dest}")
        while len(session._BRAINS) >= max(1, keep):
            session._BRAINS.pop(next(iter(session._BRAINS)))
        return fb.Brain.load(spec, dest / entry["file"])

    session.BRAIN_LOADER = load
    return manifest
