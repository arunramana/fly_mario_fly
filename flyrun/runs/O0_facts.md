# O0: facts for the "?"-block and mushroom scenes

Facts only. No behaviour code, no new knobs, the default brain / senses / motor are untouched (every scratch build lives in memory; `tutorials/_cache/W_steer.npy` is unchanged and the scratch builder reproduces it exactly, max |diff| = 0).
Code: `flyrun/o0_graph.py` (graph queries), `o0_sim.py` (scratch builds + drives), `o0_motor.py` (motor check + baseline), `o0_ram.py` (RAM / tiles / mushroom / removal / M2 setup).
Numbers: `runs/O0_*.csv|json`. Graph work uses the project's edge table with >= 5 synapses per connection (`data/derived/brain_edges_N5.npz`) - so "direct" below means an edge of >= 5 synapses.
Units: the sim is the Knobs-default dynamics (G 0.5, alpha 0.3, 10 substeps, clip 50); "level" = a constant current into each driven neuron; the press threshold is TTMn 0.10.

## 1. Hearing -> jump (Johnston's organ -> Giant Fiber)

**Johnston's organ in MaleCNS** (`runs/O0_jo_types.csv`): 672 neurons, all type names `JO-*`, class `mechanosensory`, by subclass: **auditory 114** (JO-A1 8, A2 13, A3 2, A4 2, A-unclear 24; JO-B1_a 14, B1_b 11, B1_c 9, B2 2, B3 4, B-unclear 13; CA1 2, CA2 6; unclear 4), wind/gravity 475 (JO-C*, JO-E* ...), grooming 65 (JO-F*). Some type names appear under two subclasses (e.g. JO-B1_a). The GF is DNp01 (bodies 10001, 10010).

| source | n | direct edges onto GF | direct synapses | share of GF's total input | linear mass onto GF, 1 hop | 2 hop | 3 hop |
|---|---|---|---|---|---|---|---|
| JO auditory | 114 | 20 | 689 | 1.6 % | 0.028 | -0.002 | -0.001 |
| JO wind/gravity | 475 | 0 | 0 | 0 | 0 | +0.002 | -0.002 |
| JO all | 672 | 20 | 689 | 1.6 % | 0.028 | -0.001 | -0.003 |
| **LC4** | 126 | 126 | 6362 | 14.6 % | 0.291 | 0.020 | -0.001 |
| **LPLC2** | 185 | 176 | 4836 | 11.1 % | 0.224 | 0.024 | +0.001 |
(mass = signed sum of W[j,i] = sign_i x synapses / total input of j along walks of that length, summed over source and target neurons.)

- **Direct JO -> GF**: only auditory neurons: **JO-B1_a** (13 neurons; 518 synapses onto the left GF, 23 onto the right), **JO-B1_c** (6 neurons, 138 onto the left GF), **JO-CA1** (1 neuron, 10 onto the left GF). Strongly lateralised to the left GF.
- **2-hop** JO -> X -> GF, top intermediate types by |mass| (auditory JO): SAD109 (-0.0022; 223 syn in, 360 out), SAD064 (+0.0019; 502 / 667), SAD096 (-0.0011), SAD107 (-0.0007), SAD103 (-0.0007), CB0307 (-0.0006), DNge130 (+0.0005), SAD053 (+0.0004), CB2664 (+0.0003 auditory / +0.0034 for all JO). Net 2-hop mass is of mixed sign and ~10x smaller than the direct route.
- **Versus looming**: per neuron the JO -> GF synapses are as large as LC4's (about 34 vs 50 synapses per neuron) but there are only 20 of them against 311 detectors: in aggregate the direct JO route is **~10x (LC4) / ~8x (LPLC2) weaker** in mass.
- **In W_steer?** None. 0 JO neurons, 0 ORN neurons (W_steer = 636: LC4 126, LPLC2 185, LC10a 275, AOTU/LAL intermediates, TTMn, DNp01, DNp09, DNa01/02).
- **Smallest addition with the same k = 3 / N = 5 rule** (every neuron on a <= 3-hop walk of >= 5-synapse edges from auditory JO to GF/TTMn): **969 neurons, 854 not in W_steer** (71 JO, 398 at 1 hop, 385 at 2 hops; types e.g. JO-A2, JO-B1_a/b/c, JO-A1, CB1638, PVLP123, AMMC035, GFC2, CB4118, ...). All JO: 2,441 (2,225 new). **The thin variant**: just the **20 JO neurons with a >= 5-synapse edge onto the GF** (13 JO-B1_a, 6 JO-B1_c, 1 JO-CA1), i.e. the 1-hop slice of that rule.

**Scratch builds** (W_steer + additions; edges touching a new neuron kept if >= 5 synapses; every row re-normalised by its in-network input, as W_steer was):

| build | neurons | looming replay: GF peak / TTMn peak | crosses TTMn 0.10 |
|---|---|---|---|
| W_steer (default) | 636 | 0.208 / 0.1033 | yes, at the frame of the first press (frame 50 of the approach) |
| + 20 direct JO | 656 | 0.207 / 0.1028 | yes, same frame (looming unchanged) |
| + full k/N auditory set | 1,490 | 0.052 / **0.0021** | **no** (the 854 new neurons dilute every row; looming no longer triggers: it would need re-calibration) |
(The looming replay feeds the logged theta / dtheta of the S3e smoke run's approach to the first Goomba into LPLC2-R / LC4-R with HOME_R 0.5. The steady input at the median trigger is theta 44.3 deg, dtheta 0.0635 rad/frame (18 onsets): default GF 0.221, TTMn 0.1105.)

**Driving JO alone** (constant level into each of the 20 JO neurons; 100 frames; `runs/O0_jo_drive.csv`):

| level | 1 | 2 | 5 | 10 | 20 | 50 |
|---|---|---|---|---|---|---|
| GF peak | 0.031 | 0.062 | 0.154 | 0.308 | 0.615 | 1.234 |
| TTMn peak | 0.015 | 0.031 | 0.077 | **0.154** | 0.308 | 0.617 |
| TTMn >= 0.10 | no | no | no | yes | yes | yes |
- **JO alone pushes TTMn over the press threshold from level 6.5** (bisection), where GF is about 0.20, the same GF peak as the looming approach (0.208). Linear in the level (TTMn = GF / 2). For scale, the looming input on the detectors at the trigger is 0.77 per LPLC2-R neuron and 0.064 per LC4-R neuron: JO needs ~8x the per-neuron input of LPLC2.
- DNp09 stays ~0 (1e-5): JO does not make him walk.
- With the full k/N auditory set (71 JO driven, level 50): GF 0.41, TTMn 0.0013, DNp09 0.009: **no** press at any level up to 50.

## 2. Smell -> steering (attractive ORN -> DNa)

- **ORN types**: the project's attractive food set (docs/INVESTIGATION_phase3.md): **ORN_DM1 (Or42b), ORN_VA2 (Or92a), ORN_DM4 (Or59b)**. Counts per antenna (side from the instance suffix): DM1 L 35 / R 39, VA2 L 33 / R 41, DM4 L 16 / R 15; **left antenna 84, right 95**.
- **Path to DNa**: 0 direct synapses, **minimum 3 hops** to DNa L and DNa R from either antenna (ORN -> uniglomerular PN -> X -> DNa; the DNa-side hop is 2 hops from the ORNs). The cells that are 2 hops from the ORNs and 1 hop from DNa (synapses ORN-side / DNa-side): left antenna DNae007 (12 / 268), LAL030_a (205 / 186), LAL011 (99 / 160), LAL030_b (135 / 143), CB0356 (160 / 122), LAL051, pIP1, AVLP299_d; right antenna LAL030_a (76 / 158), LAL030_b (122 / 143), CB0356 (123 / 122), VES087, VES046, MBON32, AVLP299_c.
- **3-hop mass** (`runs/O0_orn_to_dna.csv`, all attractive ORNs): left antenna -> DNa_L 1.9e-5, -> DNa_R 6.2e-6 (3x ipsilateral); right antenna -> DNa_L 1.5e-5, -> DNa_R 1.8e-5 (weakly ipsilateral). About 1e-5, i.e. 4-5 orders below the looming route.
- **In our model?** No (0 ORN neurons). **Smallest addition with the k/N rule**: the 3-hop set from the attractive ORNs to DNa: **240 neurons (235 new)** = the 179 ORNs plus ~60 PN / LAL / AVLP / VES cells (per antenna 130 / 132).
- **Scratch drive** (W_steer + those 235; looming replay still crosses 0.10, peak 0.1033, so the base is intact). Drive = a level into each of one antenna's attractive ORNs (70 left / 84 right in the build); steer = mean DNa_R - mean DNa_L (negative = Left); motor threshold |steer| > 0.01:

| level | 1 | 2 | 5 | 10 | 20 | 50 |
|---|---|---|---|---|---|---|
| LEFT antenna: DNa_L / DNa_R | .0052 / .0031 | .0104 / .0061 | .0259 / .0153 | .0519 / .0306 | .104 / .061 | .161 / .099 |
| LEFT antenna: steer R-L | -0.0021 | -0.0043 | **-0.0107** | -0.0213 | -0.0427 | -0.0625 |
| RIGHT antenna: steer R-L | +0.0035 | +0.0071 | +0.0177 | +0.0354 | +0.0708 | +0.0973 |
  **The turn is ipsilateral** (left antenna -> DNa_L above DNa_R -> Left; right antenna -> Right). Alone, smell crosses the steering threshold from level ~5 (left) and DNp09 stays ~0 (<= 1e-3): it steers but does not make him walk. Cross-check with the thin PN bridge cast of notebook 21 (`W_odour.npy`, 843 neurons): the sign is the OPPOSITE (left antenna: steer +0.0027 at 5, +0.018 at 50; right: +0.005 / +0.029), i.e. the laterality depends on which intermediates are included - only the k/N build gives ipsilateral steering.
- **With HOME_R 0.5 on** (the M2 situation; `runs/O0_home_vs_smell.csv`, left antenna): HOME_R alone gives DNp09 0.213 and steer **+0.049** (rightward). Adding left-antenna ORN drive: steer +0.051 (1), +0.049 (2), +0.042 (5), +0.031 (10), +0.0095 (20), **-0.0104 (50)**. The net steering crosses the Left threshold (-0.01) only at level ~49 and **saturates there** (the ORN activity is clipped at 50): the maximum leftward steer smell can produce against HOME_R 0.5 is -0.0104, a margin of 0.0004 over the motor threshold.
- **ORN -> GF** (not simulated): 3 hops to the GF (DNp01) from the attractive ORNs, 4 to TTMn.

## 3. Motor check: can the fly go left?

Motor v2 (A rules unchanged), HOME_R 0.5, enemies removed, 150 frames of walking right (Mario ends at x 280), then 150 frames with the steering input (`runs/O0_motor_dnaL.csv`, `O0_motor_orn.csv`).
- **Buttons**: when steer < -0.01 the motor map returns **Left alone** (Left wins over Right; there is no Left+Right in our action list; the A press is unaffected). Otherwise Right (DNp09 0.21 keeps "walk" on).
- **(a) a scratch current into DNa_L**: steer = +0.0468 - 0.991 x current. Currents 0 - 0.05: steer +0.047 .. +0.0045, Right 100 %, dx +154. **From 0.1: steer -0.045, Left 100 %, Mario goes from x 280 to x 179 (dx -101)**, where the screen's left edge stops him (the screen never scrolls back). Net leftward motion needs steer < -0.01, i.e. a current of about 0.057 (DNa L-R > +0.01 against the +0.047 that HOME_R produces).
- **(b) the scratch ORN build, HOME_R + left-antenna ORNs**: level 20: steer +0.0098, Right 100 % (dx +154); **level 50 / 100 / 200 (identical: saturated): steer -0.0102, Left 98.7 %, Mario x 280 -> 182 (dx -98)**. So smell at the saturated drive does produce real leftward motion, with a margin of 0.0002-0.0004 on the threshold.
- Compare: the direct current needs DNa L-R ~ +0.057; the ORN route delivers at most -0.0104 net of HOME_R, i.e. just enough.

## 4. RAM and tiles (1-1)

**Tile ids** (metatile buffer, `level.tile`): "?" block **192 (0xC0) = coin**, **193 (0xC1) = power-up (mushroom)**; brick 81; stair / hard block 97; pipe 18/19 (rim) + 20/21 (body), pipe 4's rim 16/17. A scripted hit: **192 / 193 -> 35 for 13 frames (the bump animation) -> 196 (0xC4) = used block** (permanent). Hit from the ground: block 256, head bump at feet y 139 (small).

**Every "?" in 1-1** (`runs/O0_qblocks.csv`; underside above the ground under it; small Mario's feet must rise `underside - 16` px for his head to reach it; max jump 68 px):
| x | row | tile | underside above ground | rise needed (small) | reachable from the ground | contents |
|---|---|---|---|---|---|---|
| 256 | 7 | 192 | 48 | 32 | yes | coin (verified: +1 coin, no power-up slot) |
| 336 | 7 | 193 | 48 | 32 | yes | **mushroom** (verified) |
| 352 | 3 | 192 | 112 | 96 | no (from the block row below) | coin (by id) |
| 368 | 7 | 192 | 48 | 32 | yes | coin (verified) |
| 1248 | 7 | 193 | 48 | 32 | yes | **mushroom** (verified: slot 5 active, sliding) |
| 1504 | 3 | 192 | 112 | 96 | no | coin (by id) |
| 1696 | 7 | 192 | 48 | 32 | yes | coin (by id) |
| 1744 | 3 | 193 | 112 | 96 | no | mushroom (by id) |
| 1744 | 7 | 192 | 48 | 32 | yes | coin (by id) |
| 1792 | 7 | 192 | 48 | 32 | yes | coin (by id) |
| 2064 | 3 | 192 | 112 | 96 | no | coin (by id) |
| 2080 | 3 | 192 | 112 | 96 | no | coin (by id) |
(12 "?" blocks, up to x ~2800 seen by a scripted scan; a block 48 px up is hit by a ground jump holding A for ~9-10 frames; the row-3 blocks need him to stand on a row-7 block or brick first.)

**The mushroom** (`runs/O0_mushroom_trace.csv`; frames relative to the bump frame):
- Object **slot 5** (the 6th: the five enemy slots 0-4 are the ones the senses read; slot 5 is the power-up), **type byte 0x2E** (= `E.POWERUP_ID`), active flag `0x0F + 5`, state `0x1E + 5`, x = `0x6E + 5` (page) * 256 + `0x87 + 5`, y = `0xCF + 5` (feet + 8), x speed `0x58 + 5` (signed; +16 = 1 px/frame right), y speed `0xA0 + 5`, moving direction `0x46 + 5` (1 right).
- **Emerging**: frame 0 (same frame as the bump) to frame 58: x 336, speed 0, rises from y 134 to 120 (state counter 3 -> 17, 1 px per 4 frames). **Sliding right from frame 59**, speed +16 = **1.0 px/frame**, on the brick row (y 120 = feet 112); runs off the end of the bricks at x ~394-400 and falls to the ground (y 184 = feet 176); **flips to -16 (left) at x 432 at frame 155 = pipe 1 (x 448)** and slides left at 1 px/frame.
- **Eaten**: at contact (Mario box x 379..391 vs mushroom x 391, frame 197) the active flag `0x0F + 5` goes to 0 and the slot is empty (the object is despawned); the power-up state changes in the same frame. It also despawns on its own when it leaves the screen on the left (natural M2 test: x 375 at +121 frames after hand-over, gone by +151).
- **Power-up state**: `0x0756` = 0 small, **1 big** (2 = fire); `0x0754` = size flag, 1 small, 0 big (flips ~30-40 frames after eating, during the growth animation).
- **Height**: small Mario's head bumps a block (underside y 128) at feet y 139, big Mario's at **feet y 153** (14 px higher up the jump); the player collision box `0x04AC..0x04AF` is 12 px tall small (e.g. 196..208 standing) and **24 px tall big** (161..185 at the bump) -> the sprite is 16 -> **32 px**.

**Removing enemies**: zero the active flag `0x0F + s` of the enemy slots **0-4** after every step (never slot 5, so the mushroom is untouched). First ~640 px with the scripted driver: without removal 405 frames, first enemy at frame 83, no death; with removal 372 frames, **2 enemies zeroed (the first two Goombas)**, no death, reached x 640. The mushroom hit tests above ran under removal: the mushroom emerged, slid and was eaten normally.

**Mushroom-behind setup (M2)** (`clips/O0_m2_setup.mp4`, 6 s):
- *Natural* (scripted hit at 336 and a scripted run over pipe 1, hand-over on the ground at x >= 500): Mario x 506, mushroom x 368, 138 px behind, moving **right** (+16), 1 px/frame, on the brick row. It then bounces off the pipe at x 432, goes left, and is **gone 120-150 frames after the hand-over** (off the left edge): too far behind to be useful.
- *Placed* (used for the baseline): the same run to x >= 560 (flat ground), then one RAM poke puts the mushroom **64 px behind Mario on the ground (x 496), moving right (direction 1, speed +16)**. Hand-over: Mario x 560, mushroom x 496, direction right. It stays live and moves normally (x 497, 527, 557 at frames +1, +31, +61; 1 px/frame); with Mario standing still it reaches him at ~+65 frames and is eaten (power-up state 1). With a walking Mario (1.5 px/frame or faster) it never catches up.

## 5. Baseline (S3e fly, looming on, default knobs; no smell, no hearing; enemies removed)

| run | result |
|---|---|
| A: from the start to x 651 | no "?" hit (tiles 256 / 336 / 368 never changed), **no mushroom** (slot 5 never active), power-up state 0 throughout, 0 Left presses; he jumps only at the pipes (take-offs x 397, 537; A fraction 0.17) |
| B: M2 placed setup (Mario x 560, mushroom 64 px behind moving right) | **never turns back**: 0 Left presses, min x 562, runs on to x 1700; the mushroom trails at 1 px/frame (x 527 / 557 / 587 at +30 / +60 / +90), is never eaten (power-up max 0), and is gone from the screen later |
The "?" blocks are invisible to the looming senses (a block is not an obstacle on the ground), and the fly has no route to go back: the "before" for every later scene.

## Is hearing -> GF strong enough for the "?" jump? Can steering produce real leftward motion?
**Hearing: yes, but only with a small, specific addition.** Real JO neurons do synapse on the GF: 20 auditory neurons (JO-B1_a / B1_c / CA1; 689 synapses, 1.6 % of GF input, left GF mostly), about 8-10x weaker in aggregate than LC4 / LPLC2 but cheap to add: W_steer + those 20 neurons leaves the looming response intact and **JO alone presses A from a per-neuron level of ~6.5** (GF 0.20, the same as the looming peak), so an auditory cue on those 20 neurons can drive the "?" jump with a real connection and no invented link. Adding the full k = 3 / N = 5 set (854 neurons) instead breaks the looming trigger (TTMn peak 0.002) and does not let JO reach threshold. **Smell -> GF** would be 3 hops (not measured here); we would not need it for the jump because hearing already reaches the GF directly. **Steering: yes, real leftward motion is possible**: with HOME_R on, steer < -0.01 yields Left alone and Mario walks left (x 280 -> ~180, stopped by the screen edge) for a direct DNa_L current >= ~0.06 and, through the real ORN route, only barely (steer -0.0104 at saturation, threshold -0.01): the smell can win against HOME_R 0.5 but with essentially no headroom (levels 50, 100, 200 are identical). The mushroom itself is easy to set up (slot 5, type 0x2E, 1 px/frame, bounces at pipe 1); the baseline fly never hits a "?" and never turns back for it.
