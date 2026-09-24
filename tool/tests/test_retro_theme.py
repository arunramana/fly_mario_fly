"""tool/SPEC_ui_retro.md section 5: the retro theme loads without
crashing and every @TOKEN@ placeholder in tool/ui/style.qss actually gets
substituted from tool/ui/palette_colors.py -- a typo'd token name would
otherwise ship as a literal, invalid QSS fragment silently ignored by Qt.
"""
from __future__ import annotations

import re

from tool.ui import palette_colors
from tool.ui.app import FONT_PATH, STYLE_QSS_PATH, load_theme


def test_font_and_qss_files_exist_on_disk():
    assert FONT_PATH.exists()
    assert STYLE_QSS_PATH.exists()


def test_load_theme_leaves_no_unsubstituted_token(qapp):
    load_theme(qapp)
    stylesheet = qapp.styleSheet()
    assert stylesheet, "load_theme() did not apply a stylesheet"
    leftover = re.findall(r"@[A-Z_]+@", stylesheet)
    assert not leftover, f"unsubstituted QSS tokens: {leftover}"


def test_every_palette_colour_actually_appears_in_the_applied_stylesheet(qapp):
    load_theme(qapp)
    stylesheet = qapp.styleSheet()
    for name in ("SKY_BLUE", "MARIO_RED", "LUIGI_GREEN", "BRICK_BROWN", "BLACK", "WHITE"):
        value = getattr(palette_colors, name)
        assert value in stylesheet, f"{name} ({value}) never made it into the applied stylesheet"


def test_start_button_object_name_matches_the_qss_selector():
    style_text = STYLE_QSS_PATH.read_text(encoding="utf-8")
    assert "#startButton" in style_text
