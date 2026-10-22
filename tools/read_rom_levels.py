"""Read every level out of the SMB1 ROM the gym env uses and write src/fly_mario/mario/facts/level_db.json.

    python tools/read_rom_levels.py            # writes the db, prints a summary
    python tools/read_rom_levels.py --check    # exit 1 if the committed db differs from what the ROM gives

The ROM format (area objects, enemy objects, header bits, area pointers) is from the community SMB disassembly
("smbdis.asm"); see src/fly_mario/mario/leveldata/. The db is generated and committed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from fly_mario.mario import leveldata
from fly_mario.mario.leveldata import build


def dumps(obj, depth=0, max_depth=3) -> str:
    """JSON where the top levels are indented and anything deeper sits on one line (small, diff-friendly)."""
    if depth >= max_depth or not isinstance(obj, (dict, list)) or not obj:
        return json.dumps(obj, separators=(", ", ": "))
    pad, pad2 = " " * depth, " " * (depth + 1)
    if isinstance(obj, dict):
        body = ",\n".join(f"{pad2}{json.dumps(k)}: {dumps(v, depth + 1, max_depth)}" for k, v in obj.items())
        return "{\n" + body + "\n" + pad + "}"
    if all(not isinstance(v, (dict, list)) for v in obj):
        return json.dumps(obj, separators=(", ", ": "))
    return "[\n" + ",\n".join(pad2 + dumps(v, depth + 1, max_depth) for v in obj) + "\n" + pad + "]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = dumps(build.build()) + "\n"
    path: Path = leveldata.DB_PATH
    if args.check:
        same = path.exists() and path.read_text(encoding="utf-8") == text
        print("level_db.json is up to date" if same else "level_db.json differs from the ROM")
        return 0 if same else 1
    path.write_text(text, encoding="utf-8")
    db = json.loads(text)
    print(f"wrote {path} ({len(text) / 1024:.0f} KB): {len(db['areas'])} areas, {len(db['stages'])} stages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
