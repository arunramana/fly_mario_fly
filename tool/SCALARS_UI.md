# Display scalars

Every hand-set, DISPLAY-ONLY scalar in the tool (never read by the
simulation -- see `tool/core/display_params.py`'s own docstring),
generated from that file. Regenerate after any change to it:

```
.venv/Scripts/python.exe -m tool.core.display_scalars_doc
```

`tool/tests/test_display_scalars_doc.py` fails if this file and
`tool/core/display_params.py` disagree. The simulation's own scalars are
tracked separately in `docs/SCALARS.md`, generated from
`config/params.py`.

## PaletteDisplayParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `mario_x_margin_px` | `8.0` | unknown | invented (the sprite's own pixels aren't perfectly aligned to mario_x as a left edge in every animation frame) | `tool/core/palette.py (MARIO_X_MARGIN_PX)` |
| `mario_y_min_px` | `140.0` | unknown | measured (a real 689-frame run, level 1-1: near-Mario red pixels stayed within roughly rows 190-239 in the common case; 140 gives headroom through a generous jump apex) | `tool/core/palette.py (MARIO_Y_MIN)` |

## PreviewBarParams

| field | value | range | provenance | home |
|---|---|---|---|---|
| `bar_max_lc4` | `4.0` | unknown | measured (a real 689-frame run, level 1-1, sigma=0, seed=0: observed max ~3.36) | `tool/ui/widgets/preview.py (_BARS)` |
| `bar_max_lplc2` | `6.0` | unknown | measured (same run: observed max ~5.49) | `tool/ui/widgets/preview.py (_BARS)` |
| `bar_max_dna01` | `12.0` | unknown | measured (same run: observed max ~10.4) | `tool/ui/widgets/preview.py (_BARS)` |
| `bar_max_dna02` | `12.0` | unknown | measured (same run: observed max ~10.4) | `tool/ui/widgets/preview.py (_BARS)` |
| `bar_max_dnp09` | `1.0` | unknown | measured (same run: observed max ~0.94, a bounded [0,1] output) | `tool/ui/widgets/preview.py (_BARS)` |
| `bar_max_mdn` | `12.0` | unknown | invented (no dedicated MDN run measured yet -- same WTA-style circuit shape as dna01/dna02, so its ceiling borrows theirs until MDN gets its own measured run) | `tool/ui/widgets/preview.py (_BARS)` |

## Totals

**8 display-only scalars.** Two related values are deliberately NOT here -- they duplicate an existing simulation scalar and are read directly instead: `tool/core/palette.py`'s Mario sprite width reads `config.entity.entity_width_px`; `tool/ui/widgets/preview.py`'s TTMn bar max reads `config.jump.spike_amp`.
