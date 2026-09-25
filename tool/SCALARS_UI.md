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
| `mario_y_offset_px` | `19.0` | unknown | measured (tool/core/palette.py's own probe script: held right+A through a full jump arc on a real 1-1 env, compared ram[0x03B8] each frame against the topmost red-dominant screen row within Mario's own x-column band; the two track 1:1 with an offset that ranged 17-22px across the jump's animation frames, ~19px on average) | `tool/core/palette.py (MARIO_Y_OFFSET_PX)` |
| `mario_height_px` | `40.0` | unknown | invented (generous: covers small (16px) or big/fiery (32px) Mario's sprite height plus the ~5px offset variance the same probe measured across animation frames, the same margin-for-slop role mario_x_margin_px plays horizontally) | `tool/core/palette.py (MARIO_HEIGHT_PX)` |

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

**9 display-only scalars.** Two related values are deliberately NOT here -- they duplicate an existing simulation scalar and are read directly instead: `tool/core/palette.py`'s Mario sprite width reads `config.entity.entity_width_px`; `tool/ui/widgets/preview.py`'s TTMn bar max reads `config.jump.spike_amp`.
