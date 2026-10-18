# S1 — senses v2 (flyrun)

`Knobs.SENSES_VERSION`: "v1" (default, every Part 1–7 config/genome/test) | "v2" (`flyrun/senses_v2.py`, chosen in `run.py`). v1 code paths are untouched; the full flyrun suite passes (56 tests: 45 existing + 11 new, `tests/test_senses_v2.py`), including the r3 replay (1405.1) and a v1 replay of the 7e final genome on HOLDOUT ep0 (max_x 1532 = the logged value). No motor, search, or fitness change.

## RAM facts verified empirically (scripted driver through all of 1-1, per-frame RAM dump, flag reached; small Mario throughout, power state 0)
- **Mario y = `0x00CE`** is Mario's **feet** y in tile-buffer coordinates: 176 on the ground (= top of tile row 11, 16·11), 112 on the floating ledge (top of row 7), continuous through jumps (e.g. 171 → 146 rising). Screen y = this + 32 (HUD offset; used to draw the boxes, which land on the sprites).
- **Enemy y = `0x00CF`+slot** = feet y **+ 8**: Goomba and Koopa on the ground read 184 (surface 176), a Goomba on the ledge reads 120 (surface 112).
- **Type byte `0x0016`+slot**: `0x06` Goomba (2554 frames seen), `0x00` green Koopa (159 frames, x 1613–1712), `0x31` something at x 3264 (flag area; ignored). Others never appeared in 1-1 and are ignored.
- **Enemy state `0x001E`+slot** (Goomba): 0 walking, 1 just appeared / dropping from a higher row, 4 stomped (the byte flips when Mario bounces off it, Fix 1), 0x22 defeated/falling. v2 treats a Goomba as a threat only in states 0/1, a Koopa in state 0.
- **NOT verified:** the shell. The scripted run never stomps the Koopa, so I have no RAM for a shell; v2 assumes "type 0x00 in state 2 or 3" and sizes it 16×16. Treat shells as untested.
- Contact geometry check: in Fix 1, Mario died with a Goomba 12 px ahead, so Mario's box is 12 wide (`MARIO_BOX` = 12×16, gap 0 at dx 12).

## What v2 does (`senses_v2.py`)
One threat per frame (nearest by 2-D box gap, ahead = object left edge ≥ Mario's left edge): live enemies, the nearest rising wall/pipe/step column (height = column top above Mario's feet, floored at 0), each empty floor tile (16 px, `PIT_GAIN_V2` = 1, the evolved PIT_GAIN ignored). θ = 2·atan(h/2d), d floored at 1 px as in v1; dθ per object identity, 0 at a target switch. Floating blocks, threats behind, unknown enemy types: ignored. The same R-side inputs (LC4_R, LPLC2_R, LC10a_R) as v1. New scalars (all INVENTED (fixed), in `knobs.py` and its registry): SENSES_VERSION, SIZE_TABLE, ENEMY_TYPES, MARIO_BOX, ENEMY_FEET_OFFSET, PIT_GAIN_V2.

## Smoke run (default knobs, v2, σ 0, noop 0; motor still the old hold/cooldown; `runs/S1_smoke_log.csv`, `clips/S1_senses_v2.mp4` = 10.6 s at 0.5×)
max_x **723**, ends "stuck", wall H64 @736 (pipe 3) — the same place v1's default run ends (Part 3). Chosen-threat sequence: Goomba #1 (from d 179 down to 30; first A at d 20, θ 44° as before) → pipe 1 face (130 → 26) → a far Goomba → pipe 2 face → Goomba → pipe 2 face adjacent (d 1) → Goomba → pipe 3 face. The clip draws a red box on a Goomba, blue on a face, magenta on a pit tile.

## Things in the spec that didn't fit the game
- **Saturation at contact is still there.** A face adjacent to Mario has d = 1 (floor), so θ = 2·atan(h/2) ≈ 170° for a 48 px column (θ_max 2.98–3.06 rad in the log), the same d→0 saturation CLAUDE.md warns about; the spec's gap definition makes it unavoidable unless a larger floor is chosen (not done; no tuning in S1).
- **No visibility limit for enemies**: a Goomba 165–179 px ahead (θ ≈ 6°) is the chosen threat whenever nothing nearer exists, as in v1.
- **"Nearest by gap" lets a far enemy beat a face that is only briefly nearest** and vice versa; with one channel, the face of the next pipe is shadowed by any nearer Goomba (and the reverse) — the intended "next immediate threat" behaviour, but worth watching in S2.
- Pit tiles under Mario's own left half count as "ahead" when their left edge ≥ Mario's left edge, so a half-crossed pit tile can stay a threat at d ≈ 0; not exercised in the smoke run (it stops at pipe 3), so **pits are tested synthetically only**.
- Mario's size is only correct for small Mario; big Mario is not handled (never occurs in these runs).
