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
