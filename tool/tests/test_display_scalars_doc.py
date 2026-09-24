# What this file does, in plain English:
# Checks that tool/SCALARS_UI.md, the document listing the tool's own
# display-only numbers, is exactly what the generator in
# tool/core/display_scalars_doc.py produces now.
"""tool/SCALARS_UI.md must equal tool.core.display_scalars_doc.generate().
Mirrors tests/test_scalars_doc.py for the tool's own (non-simulation)
scalars.
"""
from __future__ import annotations

from tool.core.display_scalars_doc import SCALARS_MD_PATH, generate


def test_scalars_ui_md_matches_generator():
    on_disk = SCALARS_MD_PATH.read_text(encoding="utf-8")
    assert on_disk == generate(), (
        "tool/SCALARS_UI.md is out of date -- regenerate with "
        "`.venv/Scripts/python.exe -m tool.core.display_scalars_doc`"
    )
