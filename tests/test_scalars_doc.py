"""REFACTOR_PLAN.md phase 4: docs/SCALARS.md must be exactly what
config/scalars_doc.generate() produces -- if this fails, someone edited
config/params.py without regenerating the doc (or vice versa). Same
discipline as tests/golden/, applied to a document instead of a CSV."""
from __future__ import annotations

from config.scalars_doc import SCALARS_MD_PATH, generate


def test_scalars_md_matches_generator():
    on_disk = SCALARS_MD_PATH.read_text(encoding="utf-8")
    assert on_disk == generate(), (
        "docs/SCALARS.md is out of date -- regenerate with "
        "`.venv/Scripts/python.exe -m config.scalars_doc`"
    )
