"""The bundle: every file the lite server needs, so it runs with no MaleCNS data and no emulator set-up.

    python -m fly_mario_fly.lite.bundle <dest> [--levels 1-1,1-2]      (on a machine that has the data, once)

    brains/manifest.json, brains/*.npz   the cached brains of every mechanism set (~41 MB in all)
    panels/<brain>.npz                   what the video's brain panel draws: soma positions, colours, index rows (small)
    registry.json  levels.json  flies.json  fly_blank.json   the answers the page asks for before a run
    thumbs/<level>.png  icons/<object>.png                  pictures
    version.txt                                             part of every cache key: a new bundle never serves an old video
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from fly_mario_fly import lite
from fly_mario_fly.lite.config import LiteConfig


class Files:
    """Read-only access to a bundle folder. A name that tries to leave the folder is refused."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def path(self, *parts: str):
        p = self.root.joinpath(*parts).resolve()
        return p if self.root in p.parents else None

    def read(self, name: str) -> bytes:
        p = self.path(name)
        if p is None or not p.exists():
            raise FileNotFoundError(f"{name} is not in the bundle {self.root}")
        return p.read_bytes()


def read_version(bundle_dir: Path) -> str:
    return (Path(bundle_dir) / "version.txt").read_text(encoding="utf-8").strip()


def with_version(cfg: LiteConfig) -> LiteConfig:
    """The config with `version` = code version + bundle fingerprint (every cache key includes it)."""
    return replace(cfg, version=f"{lite.VERSION}-{read_version(cfg.bundle_dir)}")


def build(dest: Path, data_root: Path, levels: tuple = ("1-1", "1-2")) -> dict:
    from fly_mario_fly.api import convert as V
    from fly_mario_fly.api import icons, ports
    from fly_mario_fly.runner import brainstore, load_fly
    from fly_mario_fly.runner.config import FLIES
    from fly_mario_fly.runner.levels import level_thumbnail
    from fly_mario_fly import registry

    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    brainstore.export_brains(Path(data_root), dest / "brains")
    from fly_mario_fly.lite import panel
    panel.export(dest, brainstore.all_specs())
    # the catalogue reads this machine's saved runs for "cleared / dies at x": a public server shows no one's history
    lv = [d.model_copy(update={"status": "open", "status_text": ""}) for d in ports.level_catalogue() if d.id in levels]
    missing = sorted(set(levels) - {d.id for d in lv})
    if missing:
        raise ValueError(f"unknown level(s) {missing}")
    dump = lambda name, obj: (dest / name).write_text(json.dumps(obj, indent=None, separators=(",", ":")), encoding="utf-8")
    dump("registry.json", json.loads(V.registry_info(lv, ["blank"]).model_dump_json()))
    dump("levels.json", [json.loads(d.model_dump_json()) for d in lv])
    fly = load_fly(FLIES / "blank.yaml")
    dump("flies.json", [json.loads(V.fly_summary(fly).model_dump_json())])
    dump("fly_blank.json", json.loads(V.fly_to_view(fly).model_dump_json()))
    (dest / "thumbs").mkdir(exist_ok=True)
    for d in lv:
        (dest / "thumbs" / f"{d.id}.png").write_bytes(level_thumbnail(d.id))
    (dest / "icons").mkdir(exist_ok=True)
    no_icon = []
    for name in registry.list_plugins("objects"):
        p = icons.get_icon(name)
        if p is None:
            no_icon.append(name)
        else:
            shutil.copyfile(p, dest / "icons" / f"{name}.png")
    h = hashlib.sha256()
    for name in ("brains/manifest.json", "registry.json", "levels.json", "fly_blank.json"):
        h.update((dest / name).read_bytes())
    for p in sorted((dest / "panels").glob("*.npz")):
        h.update(p.read_bytes())
    (dest / "version.txt").write_text(h.hexdigest()[:12], encoding="utf-8")
    size = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())
    return {"bytes": size, "levels": [d.id for d in lv], "icons_missing": no_icon}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dest", type=Path)
    ap.add_argument("--levels", default="1-1,1-2")
    ap.add_argument("--data", type=Path, default=None, help="MaleCNS data folder (default $FLY_MARIO_FLY_DATA)")
    a = ap.parse_args(argv)
    data = a.data or (Path(os.environ["FLY_MARIO_FLY_DATA"]) if os.environ.get("FLY_MARIO_FLY_DATA") else None)
    if data is None:
        ap.error("pass --data or set FLY_MARIO_FLY_DATA (a folder where the full tool has built its brains)")
    out = build(a.dest, data, tuple(x for x in a.levels.split(",") if x))
    print(f"bundle written to {a.dest}: {out['bytes'] / 1e6:.1f} MB, levels {out['levels']}")
    if out["icons_missing"]:
        print(f"no icon yet for {out['icons_missing']}: start the full tool once so the icon maker runs, then build again", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
