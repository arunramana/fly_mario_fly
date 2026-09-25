# What this file does, in plain English:
# The tool's own hand-picked display numbers -- things like how big a
# progress bar's "full" value is, or how much padding the Luigi recolour
# uses around Mario. None of these ever touch the simulation: two
# identically-run episodes produce byte-identical telemetry regardless of
# what's in this file. tool/SCALARS_UI.md is generated from it.
"""tool/core/display_params.py -- tool/SPEC_ui_retro.md section 2: display-
only scalars this session's own bug-fix pass introduced
(tool/core/palette.py, tool/ui/widgets/preview.py), kept separate from
config/params.py's simulation scalars for the same reason config.json and
tool.json are separate files. Same shape as config/params.py's own `_f`
(typed, ranged, provenance-documented dataclass field); tool/SCALARS_UI.md
is generated from this file the same way config/scalars_doc.py generates
docs/SCALARS.md.

Two related values are deliberately NOT fields here -- they duplicate an
existing simulation scalar and are read directly instead of re-declared:
`tool/core/palette.py`'s Mario sprite width reads
`config.entity.entity_width_px`; `tool/ui/widgets/preview.py`'s TTMn bar
max reads `config.jump.spike_amp`. `NES_WIDTH_PX`/`NES_HEIGHT_PX`
(palette.py) stay plain module constants -- the NES's actual screen
resolution is a hardware fact, not a hand-set choice with a provenance
story.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields

Range = tuple[float, float] | None


def _f(default, range: Range, provenance: str, home: str):
    return field(default=default, metadata={"range": range, "provenance": provenance, "home": home})


@dataclass(frozen=True)
class PaletteDisplayParams:
    """tool/core/palette.py's Luigi-recolour window. mario_y_offset_px/
    mario_height_px replaced a fixed rows-140-240 band once ADDR_MARIO_Y
    was fixed to 0x03B8 (codebase: fix ADDR_MARIO_Y to 0x03B8) and could
    finally drive a box that actually follows a jump instead of a
    generous static guess."""
    mario_x_margin_px: float = _f(8.0, None,
                                    "invented (the sprite's own pixels aren't perfectly aligned to "
                                    "mario_x as a left edge in every animation frame)",
                                    "tool/core/palette.py (MARIO_X_MARGIN_PX)")
    mario_y_offset_px: float = _f(19.0, None,
                                    "measured (tool/core/palette.py's own probe script: held right+A "
                                    "through a full jump arc on a real 1-1 env, compared ram[0x03B8] "
                                    "each frame against the topmost red-dominant screen row within "
                                    "Mario's own x-column band; the two track 1:1 with an offset that "
                                    "ranged 17-22px across the jump's animation frames, ~19px on "
                                    "average)",
                                    "tool/core/palette.py (MARIO_Y_OFFSET_PX)")
    mario_height_px: float = _f(40.0, None,
                                  "invented (generous: covers small (16px) or big/fiery (32px) "
                                  "Mario's sprite height plus the ~5px offset variance the same probe "
                                  "measured across animation frames, the same margin-for-slop role "
                                  "mario_x_margin_px plays horizontally)",
                                  "tool/core/palette.py (MARIO_HEIGHT_PX)")


@dataclass(frozen=True)
class PreviewBarParams:
    """tool/ui/widgets/preview.py's live-preview bar ceilings -- per-
    population, not a uniform guess (see that module's own comment on why
    a uniform 5.0 pinned TTMn at 100% instantly)."""
    bar_max_lc4: float = _f(4.0, None,
                              "measured (a real 689-frame run, level 1-1, sigma=0, seed=0: observed "
                              "max ~3.36)", "tool/ui/widgets/preview.py (_BARS)")
    bar_max_lplc2: float = _f(6.0, None,
                                "measured (same run: observed max ~5.49)",
                                "tool/ui/widgets/preview.py (_BARS)")
    bar_max_dna01: float = _f(12.0, None,
                                "measured (same run: observed max ~10.4)",
                                "tool/ui/widgets/preview.py (_BARS)")
    bar_max_dna02: float = _f(12.0, None,
                                "measured (same run: observed max ~10.4)",
                                "tool/ui/widgets/preview.py (_BARS)")
    bar_max_dnp09: float = _f(1.0, None,
                                "measured (same run: observed max ~0.94, a bounded [0,1] output)",
                                "tool/ui/widgets/preview.py (_BARS)")
    bar_max_mdn: float = _f(12.0, None,
                              "invented (no dedicated MDN run measured yet -- same WTA-style circuit "
                              "shape as dna01/dna02, so its ceiling borrows theirs until MDN gets its "
                              "own measured run)",
                              "tool/ui/widgets/preview.py (_BARS)")


ALL_DISPLAY_PARAM_CLASSES = (PaletteDisplayParams, PreviewBarParams)


def scalar_count() -> int:
    return sum(len(fields(cls)) for cls in ALL_DISPLAY_PARAM_CLASSES)
