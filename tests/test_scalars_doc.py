# What this file does, in plain English:
# Checks that docs/SCALARS.md, the document listing the hand-set numbers,
# is exactly what the generator in config/scalars_doc.py produces now. If
# it fails, the settings changed and the document needs regenerating.
"""
docs/SCALARS.md must equal config/scalars_doc.generate(). If this fails,
config/params.py changed without regenerating the doc.
"""
from __future__ import annotations

from config.scalars_doc import SCALARS_MD_PATH, generate


def test_scalars_md_matches_generator():
    on_disk = SCALARS_MD_PATH.read_text(encoding="utf-8")
    assert on_disk == generate(), (
        "docs/SCALARS.md is out of date -- regenerate with "
        "`.venv/Scripts/python.exe -m config.scalars_doc`"
    )
