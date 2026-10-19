# L2b: 1-2 perception facts, headroom facts, aversive-smell wiring (base 36dbc3a, branch l2b; facts only: no gain, rule or controller change)

**Result.** (1) Every 1-2 tile id the scanner missed is now decoded from the emulator, and the piranha plant and type 0x03 (= the **red Koopa**) are read; all of it is gated on `FLYRUN_LEVEL=1-2`, so **1-1 is button-identical (1947 / 1947 frames, every column equal)**. The 1-2 arm A noop 0 sigma 0 baseline is **also identical (dies x 890 to the same Koopa, 572 frames)**: nothing new is in view before the pillar. Past it (diagnostic scans, enemies removed or star-invincible, not scored) the new decoding changes what he reads at the x 1920 pit and then **he stops at the level's exit wall (x 2674) where the old blindness let him walk in**. (2) `level.headroom()` returns `(ceiling_y, rise)`; at the x ~ 890 pillar it is `(160, 0)`, on open 1-1 ground `(0, 68)`. (3) **The aversive CO2 channel (ORN_V) turns him TOWARD the smell, not away**: right antenna driven at 1-60 gives steer +0.042 -> +0.401, never negative. DA2 / DL5 do nothing to the steering.

Code: `level.py` (per-level tile tables, `headroom`), `knobs.py` (`enemy_types()`, piranha size), `senses_v2.py` (`enemy_boxes` reads the piranha / red Koopa, clipped at the rim), `l2b_tiles.py`, `l2b_enemies.py`, `l2b_structures.py`, `l2b_smell.py`, `l2b_ref.py`, `l2_scan.py` (+ `L2_SUFFIX`), `tests/test_l2b.py` (5 tests). Data: `runs/L2b_tiles.json`, `L2b_tiles_1-1.json`, `L2b_enemies.json`, `L2b_structures.csv`, `L2b_columns.csv`, `L2b_fixture_1-2_x832_960.json`, `L2b_smell*.{json,csv}`, `L2b_ref_*`, `L2_scan_A_rescue{,_star}_l2b.{csv,json}`.

## 1. 1-2 perception facts

### 1a. Tile ids, tested on the emulator (`python -m flyrun.l2b_tiles [1-2|1-1]`)
Method: the L2 scan traversal (arm A, enemies removed, pit rescue) walks the level; whenever an id has a cell on screen the emulator is backed up, small Mario is poked next to the cell, the game runs a few frames, and the state is restored. **DROP** = feet 3 px above the cell, solid if he lands within 6 px of its top (free fall would be 20+ px lower); **BUMP** = head just under the cell moving up, solid if the rise stops at once; **SIDE** = walking Right into it with y frozen, solid if x is blocked. The neighbouring cells are blanked inside the backup so every cell can be tested. Controls (`forced`, an id written into an empty sky cell): 0 -> not solid on all three tests; 35 (bumped block) and 196 (used block) -> solid on all three; 194 -> not solid. Counts below are tests that said solid / tests run.

| id | what (from stills + cells) | drop | bump | side | solid | wall / step face | rim | ceiling |
|---|---|---|---|---|---|---|---|---|
| 16, 17 | pipe rim, left / right (the 3-high pipe at x 1648, rows 8) | 1/1 | 1/1 | 1/1 | yes | yes (RIM_TILES, rim=True as in v2) | yes | yes |
| 18, 19 | pipe rims of the 4-high (row 7) and 2-high (row 9) pipes | 3/3 | 3/3 | 3/3 | yes | yes (SOLID_WALL) | no | yes |
| 20, 21 | pipe bodies, also the vertical pipe that hangs from row 0 at the exit | 5/6, 5/5 | 6/6, 5/5 | 6/6, 5/5 | yes | yes | no | yes |
| **82** | **underground brick**: ceiling row 0, side walls, floating blocks, platforms, 3-4 high walls (285 cells, rows 0-10) | 4/6 | 6/6 | 6/6 | **yes** | **yes when it stands on the floor** (e.g. the 3-high wall at x 1952, the 48 px platform at x 2560) | no | **yes** |
| 84 | ground, rows 11-12 | 4/4 | 2/4 | 2/4 | yes | no (pits stay "rows 11 and 12 empty") | no | n/a |
| **90, 92, 93, 94** | brick look-alikes, one or two cells each: rows 6, 5, 6 and 0 (row 0 = ceiling) | 2/2, 1/1, 2/2, 0/1 | 2/2, 1/1, 2/2, 1/1 | 2/2, 1/1, 2/2, 1/1 | **yes** | face if on the floor (none is: all floating) | no | **yes** |
| **28, 29, 30** | the sideways exit pipe, top row (x 2656, 2672, 2688, row 6) | 3/3 | 3/3 | 3/3 | yes | **no, deliberately** | no | yes |
| **31, 32, 33** | same pipe, bottom row; 31 = the **mouth** (row 7, x 2656) | 3/3 | 3/3 | **31: 0/1** (passes sideways), 32, 33: 2/2 | yes (31 solid from above and below, not sideways) | **no, deliberately** | no | yes |
| 36, 37 | flagpole ball and pole (x 3168, outdoor end) | 0/1, 0/6 | 1/1, 6/6 | 0/1, 0/6 | **no** | no | no | no |
| 97 | hard (stair) block | 6/6 | 6/6 | 6/6 | yes | yes | no | yes |
| 192, 193 | "?" blocks | 3/3 | 3/3 | 3/3 | yes | no (floating) | no | yes |
| 194 | coin | 0/4 | 0/4 | 0/4 | **no** | no | no | no |

Failures inside "solid" rows are test artefacts, not tiles that give way: every failed DROP is on row 0 (the cell is at the top of the buffer, Mario cannot be put above it), every failed BUMP / SIDE on ground is on row 12 (bottom of the buffer), and the flagpole's BUMP "solid" is Mario grabbing the pole. The one 20 DROP failure is on row 0 too.

**Why the exit pipe is not a face.** It is the level's door: walking Right into its mouth (31) at platform height ends the level. The first version counted 28-33 as wall tiles and the fly jumped on top of the pipe and stood under the end wall (scan stuck at x 2674-2675, cause "wall H96 @2688"); they are now solid for the ceiling test only. Section 1e shows he still gets stuck there.

**1-1, same method** (`runs/L2b_tiles_1-1.json`; used only for the headroom set, nothing in 1-1 changes): 81 (brick) 4/4/4 solid, 87 and 88 (seen at x 1616 / 1504, row 7) solid, 16-21 and 97 solid, 192 / 193 solid, 84 ground; not solid: 36 / 37 (flagpole), 96 (x 1024, row 6).

### 1b. Enemy types (`python -m flyrun.l2b_enemies`, star-invincible scan: enemies stay)
Size = the pixels the sprite draws: the frame with the enemy alive minus the frame with its slot zeroed (3 frames ahead, because the PPU draws the sprites built one frame earlier), relative to its RAM position. Cross-check: **Goomba 16 x 16 and green Koopa 16 x 24, exactly the existing SIZE_TABLE**, so the method is right.

| type byte | what | size (w x h) | notes |
|---|---|---|---|
| 0x03 | **red Koopa Troopa** (identified by the sprite in `clips/L2_stills/l2b_enemy03.png`: red shell, first at x 2317) | **16 x 24**, same as green; bottom = RAM y - 8 | states seen: 0 live, 0x22 defeated (as every enemy). Red-shell states 2 / 3 **not verified** (read as the green one). Read as kind "koopa" |
| 0x0D | **piranha plant** (first at x 1656, in the 3-high pipe at x 1648) | **16 wide, 22-24 tall when out**; bottom edge = RAM y - 8 | it lives in the pipe and is drawn behind it: fully out = its feet at the rim (RAM y 136 for a rim at y 128); partly out = only the part above the rim shows (silhouette 21-23 px, bottom 1-2 px above its feet). Reads: box top = feet - 24, height = what shows above the pipe's rim, from the tile buffer. States 0 live / 0x22 defeated. **The game activates the plant ~ 90 px before its pipe scrolls in** (first seen at screen x 346 > 256), so a plant whose pipe is not on screen is not read |
| 0x26 / 0x27 / 0x34 | the orange lifts (48 px platforms, 8 px thick) | not added | not enemies; the pits at x 2208 and 2448 still need them (L2 S2) |
| 0x31 | the flag object | n/a | |

`ENEMY_TYPES_BY_LEVEL` in `knobs.py`: 1-1 is exactly the old `{0x06, 0x00}`; 1-2 adds `{0x03: koopa, 0x0D: piranha}`. Whether the plant hurts a Mario walking past it was **not** tested (the scan is star-invincible).

### 1c. The extra pipes and structures the new scanner reads (`python -m flyrun.l2b_structures`, `runs/L2b_structures.csv`)
Faces (merged columns of equal height) and pits as the new scanner sees them over the whole level (the traversal walks with the L2 perception so it reaches the end; the recording uses the new tables):
- **Rims 16 / 17, 18 / 19**: pipes at x 1648 (48 px, plant), x 1744 (64), x 1840 (32); read as faces (rim=True, as in L2).
- **Brick faces** (82): the 3-high wall after the first x 1920 pit at **x 1952-1984, 48 px** (L2 S1: read as the floor, now a face), the 48 px platform at **x 2560-2704**, the staircase of 82 / 97 at x 2128-2208 (16-64).
- **The pipe hanging from the ceiling and the sideways exit pipe** are one structure: a vertical pipe (tiles 20 / 21) from row 0 down the end wall, and the short horizontal pipe (28-33, rows 6-7, mouth 31 at x 2656) on the 48 px platform. As faces: the platform (48) and a **176 px full-height wall at x 2704-2752**; 28-33 themselves are not faces (see 1a).
- Pits unchanged: x 1280 (48), 1920 (32), 1984 (32), 2208 (112), 2448 (112). The pit tower at 1920 now anchors to the 3-high wall: top y 96 (80 tall) where L2 had y 144 (32 tall): **the first thing that differs from L2 in the scans**.
- Outdoor end (x >= 2864): the 2-high pipe and the 8-step stair read as faces as in L2.

### 1d. Baseline (arm A, noop 0, sigma 0; `python -m flyrun.l2b_ref before|after 1-1|1-2`)
| level | before (36dbc3a) | after | button-identical |
|---|---|---|---|
| 1-1 | flag, 1947 frames, x 3161 | flag, 1947 frames, x 3161 | **yes**: the full trace CSVs are equal (every column, 1947 rows) |
| 1-2 | died x 890, enemy dx 10, 572 frames | died x 890, enemy dx 10, 572 frames | **yes**: equal (every column, 572 rows) |
So nothing new is in view up to x 890 (no bricks that form a face before it, no plant, no red Koopa). Full flyrun suite on the final code: **97 passed** (92 existing + 5 new in `tests/test_l2b.py`).

### 1e. What changed past x 890 (diagnostic scans, not scored; `L2_scan_A_rescue{,_star}_l2b.*`, compared to the L2 scans re-run on the old commit)
- Enemies removed + pit rescue: **old code reaches the flag (x 3161, 1783 frames, 6 rescues); new code stops at x 2674-2675 ("stuck", 1958 frames, 4 rescues)**. First frame that differs: 1108 (x 1832), the x 1920 pit tower above; one threat box differs before it. The new reading is right and it is what ends the run: he sees the 176 px end wall (x 2704) as a face he cannot clear, jumps at it again and again (feet 32-91, 600 frames) and never walks into the mouth of the exit pipe; with the old blindness the wall was invisible, nothing loomed, and he walked in by accident.
- Star + rescue: **piranha plant read for 25 frames** (2 plants: x 1656 and x 1752; the box shrinks 19 -> 13 px and 9 -> 6 px as the plant retracts; theta 53-163 deg at close range, A pressed: he jumps at the plant), red Koopa 0x03 read as a 16 x 24 koopa (x 2327-2347, theta 33-100 deg). Same stuck point at x 2674.
- No death or flag is a result of the fly here; these runs only show what is now read.

## 2. Headroom (`level.headroom(ram, x0, x1, feet, box_h=16)`; nothing reads it yet)
`-> (ceiling_y, rise)`: the underside y of the **lowest solid tile wholly above his head** over the columns of the span (0 = open sky), and `rise = min(MAX_JUMP_HEIGHT = 68, head - ceiling_y)` where head = feet - box_h. "Solid from below" is `level.ceiling_tiles()` (the per-level set above, plus bumped / used blocks). `runs/L2b_columns.csv` has it for every 16 px column of 1-2 at feet 176.
| scene | call | result |
|---|---|---|
| **1-2, x ~ 890 pillar** (the real tile columns, `L2b_fixture_1-2_x832_960.json`: a 3-high brick block at rows 7-9 whose underside is y 160 = his head) | `headroom(ram, 880, 892, 176, 16)` | **(160, 0)**: no rise at all (also for the spans 864-896 and 876-900) |
| 1-2, open ground just after it (x 898-910; only the row 0 ceiling) | `(898, 910, 176)` | (16, 68): a full jump |
| 1-2, brick platform x 928-959 (underside y 128) | `(930, 942, 176)` | (128, 32) |
| **1-1, open ground** | `(100, 112, 176)` | **(0, 68)** |
| 1-1, a brick 48 px above his head, big Mario | `(100, 112, 176, box_h 24)` | (128, 24) |
Where 1-2 leaves him less than a full jump (standing on the floor, columns outside walls, `L2b_structures.csv`): x 160-240 (the ? block row) 32; 464 48; 624-752 32 / 64 / 32; 832-864 32; **864-896 0 (the death pillar)**; 928-1024 32; 1072-1280 32; 1344-1440 48; 2320-2416 48. The pillar at x 864-896 is the only place with no rise at all. (L2 called it a pillar "hanging from the ceiling"; in the buffer it is a floating 3-high block, rows 7-9, with a free gap above it.) Unit tests: `tests/test_l2b.py`.

## 3. Aversive smell wiring (`python -m flyrun.l2b_smell`; scratch builds only, the production brain is untouched)
**Candidates** (MaleCNS ORN types; the literature case): **ORN_V** (the V glomerulus: Gr21a / Gr63a, **CO2**, avoided), **ORN_DA2** (Or56a, **geosmin**, avoided), **ORN_DL5** (Or7a, aversive alkenals; weaker case, Strutz 2014). Not used: DA4l, VL2p (mixed valence). Left / right counts (side from the instance name; the rest have no side):
| type | L | R | no side | in the 881-neuron model |
|---|---|---|---|---|
| ORN_V | 16 | **39** | 0 | 0 |
| ORN_DA2 | 21 | 20 | 7 | 0 |
| ORN_DL5 | 23 | 19 | 1 | 0 |
| (for scale) the attractive DM1 / VA2 / DM4 in the model | 84 | 95 | | 154 of 179 |
ORN_V is lopsided (16 vs 39); I have not checked whether that is the annotation or the animal.

**Path to DNa01/02** (>= 5-synapse edges): none has a direct or 2-hop path; **3 hops for every channel** (ORN -> PN / LN -> LAL / VES / WED -> DNa). Signed mass (hop 3): V right antenna -> DNa_R +8.1e-6, -> DNa_L +4.2e-7; V left antenna -> DNa_L +5.1e-7, DNa_R +1.2e-7; DA2 and DL5 ~ 0 (-2e-7). The hop-2 carriers of V right -> DNa_R: **CB0431 (5.9e-6)**, SIP022, CB0356, LAL030_a / b; DA2: only SAD085 (-2e-7). **Is it in our model? No**: the 881-neuron brain has none of the V / DA2 / DL5 ORNs (it has the attractive set and 62 intermediates).

**Smallest addition by the k = 3 / N = 5 rule** (neurons not yet in the 881 brain): V 58 = 52 ORNs + 6 intermediates (CB0431, M_adPNm3, M_l2PNl22, WED125, WED127, LAL030_b), 19 more of its 77 already in the model; **pruned like M2 (drop intermediates while the steering stays within 10 %): 54 = 52 ORNs + 2 intermediates (CB0431, M_adPNm3)**, right-antenna steer 0.319 / 0.401 -> 0.324 / 0.407 at level 20 / 50. DA2: 15 = 12 ORNs + 3 intermediates (SAD085, CB1824, DNpe023); DL5: 16; V + DA2 + DL5: 86 = 77 ORNs + 9 intermediates.

**Scratch drive** (881-brain + the set, HOME_R 0.5 on = the production setting, constant level into every ORN of one antenna for 100 frames; steer = mean DNa_R - mean DNa_L, so **DNa L - R = -steer**; steer < -0.01 would be Left = away from a smell on the right; `runs/L2b_smell_drive.csv`):
| build, antenna | level 0 (home alone) | 1 | 5 | 20 | 50 | 60 | DNa_L at 50 | DNa_R at 50 | min steer over 1-60 |
|---|---|---|---|---|---|---|---|---|---|
| **V, RIGHT** | +0.0424 | +0.0561 | +0.1115 | +0.3193 | **+0.4014** | +0.4014 | 0.0190 | 0.4204 | **+0.0424** |
| V, left | +0.0424 | +0.0424 | +0.0426 | +0.0430 | +0.0435 | +0.0435 | | | +0.0424 |
| V + DA2 + DL5, RIGHT | +0.0382 | +0.0506 | +0.1004 | +0.2875 | +0.3614 | +0.3614 | | | +0.0382 |
| DA2 (R or L, 1-60) | +0.0445 | = | = | = | = | = | 0.0277 | 0.0722 | +0.0445 |
| attractive ORNs, right (reference, 881 brain) | +0.0499 | | | +0.1269 (level 20) | +0.1544 | | | | |
Home alone steer is +0.0499 in the 881 brain and +0.038 to +0.045 in the builds: adding neurons shifts the DNa row normalisation a little. With HOME_R off the V right-antenna steer is also positive (+0.0135 at 1, +0.350 at 50).

**The answer, plainly: he does not turn away. A smell on the right (CO2, V) drives DNa_R up and DNa_L down, steer is positive at every level from 1 to 60, never crosses -0.01 (at any HOME_R), and saturates at +0.401 from level ~ 40.** The effect is ipsilateral, like the attractive ORNs (right antenna -> Right), but 2.6 x stronger; the left antenna's V ORNs do essentially nothing (+0.001). DA2 and DL5 have no effect on the steering at all in this graph. I did not invent a fix (a contralateral wire or a sign flip would be a new rule, not a reading of the connectome); the plain consequence is that, with the real wiring, an "aversive" smell source on one side makes him go toward it. Caveat: this only says what the DNa01/02 steering readout does with these ORNs; real CO2 avoidance may run through other descending neurons that are not in the model.

## 4. Not done / disclosed
- No clip: the 1-2 baseline is button-identical, so where he dies now is the L2 clip (`clips/L2_armA_full.mp4`); the scan results above are diagnostic, not a watchable episode.
- 1-1 headroom set (81, 87, 88, ...) comes from the same probe on 1-1; ids 35 / 196 were tested by writing them into a sky cell, not on a real bumped block.
- Red-Koopa shell states and whether the plant hurts a Mario walking past it are not verified.
- Mario's own hitbox bytes (0x04AC ...) and the lifts' sizes were tried and dropped (the slot layout I assumed did not give consistent numbers), so no number here comes from them.
- Registry rows added in `knobs.INVENTED`: `ENEMY_TYPES_BY_LEVEL / piranha size`, `EXTRA_WALL / EXTRA_SOLID / CEILING_EXTRA (level.py)`.
