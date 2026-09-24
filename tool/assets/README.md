# tool/assets/

Card images the GUI displays but does not generate itself
(`tool/SPEC_ui_retro.md` section 9). Circuit cards are the one exception
— those are generated from the real connectome
(`render.brain_panel.highlight_populations`, cached to
`tool/assets/generated/`) and need nothing from you.

Until a file below exists, its card falls back to `placeholder.png`
(shipped, already generated) — nothing crashes, nothing looks broken,
you just see a "no image" card instead of the real artwork.

## What to supply

All PNG, ideally with a transparent background (the card sits on the
retro theme's sky-blue background, `tool/ui/palette_colors.SKY_BLUE`,
`#5C94FC` — a flat, non-transparent background of a different colour
will show as a visible box around the art).

| File | Suggested size | Card |
|---|---|---|
| `tool/assets/characters/mario.png` | 256x256px | Character tab, Mario |
| `tool/assets/characters/luigi.png` | 256x256px | Character tab, Luigi |
| `tool/assets/entities/goomba.png` | 128x128px | Enemies tab, Goomba |
| `tool/assets/entities/koopa.png` | 128x128px | Enemies tab, Koopa |
| `tool/assets/entities/enemy.png` | 128x128px | Enemies tab, generic enemy fallback |
| `tool/assets/entities/powerup.png` | 128x128px | Objects tab, power-up |
| `tool/assets/entities/question_block.png` | 128x128px | Objects tab, `?` block |

Square, and at least as large as the size above — the GUI scales down to
fit (character cards render at 96x96px, entity cards at 64x64px), and a
pixel-art source shown smaller than native keeps crisp edges; scaled
*up* from something smaller will look soft or blocky.

Greyed kinds (Pit, Ground, Used block, Bricks/pipes) have no manifest
entry and always show the placeholder — they're disabled either way, so
there's nothing to supply for them.

## How this is wired

- `tool/assets/manifest.json` maps an asset id (`"mario_card"`) to one of
  the paths above, relative to `tool/assets/`.
- `tool/ui/widgets/asset_image.load_asset(asset_id)` is the only place
  any card ever loads an image — an id the manifest doesn't have, a
  manifest entry naming a file that doesn't exist, or a corrupt file all
  fall back to `placeholder.png`, never a crash.
- Adding a new asset: drop the file in place, add one line to
  `manifest.json` pointing at it. No tab code changes.

## What you do NOT need to supply

- `placeholder.png` — already generated, ships with the repo.
- Anything under `tool/assets/generated/` — circuit brain-map images,
  regenerated automatically from the connectome data the first time each
  circuit card is shown, cached after that. Gitignored on purpose (same
  reason `*.mp4`/`*.png` run output is — regenerable from data already
  on disk, not something to commit).
- `tool/assets/fonts/PressStart2P-Regular.ttf` — already bundled
  (Google Fonts, SIL Open Font License 1.1; licence text alongside it,
  `PressStart2P-OFL.txt`).
