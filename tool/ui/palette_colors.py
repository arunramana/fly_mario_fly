"""tool/ui/palette_colors.py -- tool/SPEC_ui_retro.md section 5: the
retro theme's small, named NES-accurate palette (not the full 54-colour
NES palette, just the ones actually used), as Python constants referenced
from tool/ui/style.qss rather than repeated as literal hex codes per
rule. Distinct from tool/core/palette.py's sprite-recolour module --
naming collision noted deliberately so implementation never conflates
the two.
"""

from __future__ import annotations

SKY_BLUE = "#5C94FC"      # background
MARIO_RED = "#D82800"
LUIGI_GREEN = "#00A800"
BRICK_BROWN = "#A85400"
BLACK = "#000000"
WHITE = "#FCFCFC"
