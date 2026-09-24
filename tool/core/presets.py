"""tool/core/presets.py -- named, per-tab snapshots of whatever JSON-safe
dict that tab's own preset bar hands it (tool/PLAN.md P7). Global, not
per-project: a preset is a reusable starting point ("aggressive shuffle",
"distance-only fitness"), not part of any one project's saved state.
Stored at <repo root>/tool_presets/<tab_key>/<name>.json.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PRESETS_ROOT = Path(__file__).parent.parent.parent / "tool_presets"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_ -]+$")


def _validate(tab_key: str, name: str) -> None:
    if not _SAFE_NAME.match(tab_key) or not _SAFE_NAME.match(name):
        raise ValueError(f"invalid preset tab_key/name: {tab_key!r}/{name!r}")


def _path(tab_key: str, name: str) -> Path:
    _validate(tab_key, name)
    return PRESETS_ROOT / tab_key / f"{name}.json"


def save_preset(tab_key: str, name: str, data: dict) -> Path:
    path = _path(tab_key, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_preset(tab_key: str, name: str) -> dict:
    return json.loads(_path(tab_key, name).read_text(encoding="utf-8"))


def list_presets(tab_key: str) -> list[str]:
    if not _SAFE_NAME.match(tab_key):
        raise ValueError(f"invalid preset tab_key: {tab_key!r}")
    directory = PRESETS_ROOT / tab_key
    if not directory.exists():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


def delete_preset(tab_key: str, name: str) -> None:
    _path(tab_key, name).unlink(missing_ok=True)
