# 008b — Part 7b diagnosis: the x≈1220 death of evo6/real r3 (flyrun, assisted, disclosed)

Stamp: commit c9fb390a17 +DIRTY, config 289b3d51cb29, W 5c57f81f5b1d, python 3.12.6, pip-freeze ba762955ba14

**Verdict (one line).** Class **OTHER**: the first A fires in the normal window (stim_d 40 px) and Mario then dies in the air against a **Goomba standing on a floating brick/?-block row that the fly cannot perceive**, one pixel of Goomba phase away from a stomp. Per the pre-registered decision, OTHER = **stop and report**; nothing was searched or changed. Section 5 says what the literal reading of the other classes would give, so you can overrule.

What was replayed: `warm_r3` (evo6/real restart 3 best, config `part7.yaml`) on the 10 HOLDOUT episodes through a logging wrapper (`flyrun/diagnose7b.py`; `run.py`/`motor.py` untouched, wrapper reads the Muscle state after each decision and snapshots RAM before each step). It reproduces the Part 6b result exactly (10 episodes, same max_x and end cause: 8 × x≈1220 `enemy dx=10`, 1 pit at 1129, 1 flag). Per-frame dumps: `runs/008b_replay/ep0..9.csv`; windows: `runs/008b_death_ep0_last90.csv` (frames T−90…T) and `runs/008b_flag_ep5_same_x_window.csv` (flag run over the same x range). Clips: `clips/08b_death_1219.mp4` (death run, ±3 s around x 1218, ends at the death: 14 frames after), `clips/08b_flag_same_spot.mp4` (the flag run, same spot); 30 fps playback of the 60 Hz game = 0.5×, overlay of stim_d / TTMn vs threshold / A / hold left / cooldown left / enemy slots.

## 1. What is at x≈1220 (this is not a wall)

The level map in `runs/001_level_map.csv` has no obstacle here. In RAM the tile buffer shows a **floating row of three blocks, tiles 81 / 193 (?-block) / 81 at world x 1232–1280, tile row 7** (top of the row is the standing height of a Mario at y=112; the ground Mario stands at y=176). Mario's x stalls at 1218–1220 because he is jumping against the left face of that row. Goombas (enemy y 120 = standing on the row; a ground Goomba reads 184, e.g. frames 136–160) walk along its top. A second Goomba (s1, y 56) stands on a higher brick row behind the first. `level.scan_visible` returns **no wall** for this region (`([], [(1104, 32)])`): tiles 81/192/193 are not in `SOLID_WALL`, so the fly gets **no pipe-face stimulus from the ledge**; its only stimulus is the Goomba's horizontal distance.

## 2. The 8 deaths are one trajectory; the flag run is the same trajectory

| ep | end | first A: frame / x / stim_d | A released | A re-pressed (y) | min y before x 1235 |
|---|---|---|---|---|---|
| 0 (σ0) | died x1219 | 739 / 1204 / 40 | 757 | 759 (114) | 113 |
| 1–4 (σ0) | died x1219 | x 1204 / stim_d 40 (frames 747, 761, 769, 777) | +18 | +2 (114) | 113 |
| 5 (σ.05) | **flag** | 696 / **1201 / 43** | 714 | 716 (114) | **99** |
| 6, 9 (σ.05) | died x1219 | x 1204 / stim_d 40 | +18 | +2 (114) | 113 |
| 7 (σ.05) | died x1219 | 720 / 1205 / 38 | 738 | none (died at frame 739, t=19, y 116) | 116 |
| 8 (σ.05) | pit x1129 | no A for a ledge Goomba (died earlier) | – | – | – |

Aligned on the first A (t = frames since first A), Mario's arc is **identical** in the death run and the flag run for 22 frames; the Goomba's distance matches from t=13:

| t | death x | y | s0 dx | flag x | y | s0 dx |
|---|---|---|---|---|---|---|
| 0 | 1204 | 176 | 40 | 1201 | 176 | 43 |
| 2 | 1207 | 171 | 35 | 1205 | 171 | 38 |
| 4 | 1211 | 162 | 31 | 1208 | 162 | 34 |
| 6 | 1214 | 153 | 26 | 1212 | 153 | 29 |
| 8 | 1218 | 146 | 21 | 1215 | 146 | 24 |
| 10 | 1220 | 139 | 16 | 1218 | 139 | 19 |
| 12 | 1218 | 132 | 16 | 1218 | 132 | 17 |
| 14 | 1218 | 127 | 16 | 1218 | 127 | 16 |
| 16 | 1218 | 122 | 14 | 1218 | 122 | 14 |
| 18 | 1218 | 118 | 13 | 1218 | 118 | 13 |
| 20 | 1218 | 114 | 12 | 1218 | 114 | 12 |
| 21 | 1219 | 113 | 11 | 1218 | 113 | 11 |
| 22 | 1219 | 113 | 10 | 1219 | 113 | 11 |

The only difference at the decisive frame (t=22) is the Goomba's phase: dx **10** in the death run (Mario still at the apex, y 113, A re-pressed 3 frames earlier), dx **11** then 9 in the flag run (Mario starts to descend, y 113→114, and the Goomba is handled; the flag run's Goomba later disappears from the slot list). The 3 px earlier launch (x 1201 vs 1204, from sensor noise σ0.05) moved the Goomba's arrival by ~1 px at this moment. I cannot resolve the contact rule at pixel level from the columns I logged (no sub-pixel position, no vertical speed); I do not claim a stomp-versus-side-hit mechanism beyond "same arc, 1 px of Goomba phase".

## 3. Key 40 frames each (death ep0 frames 722–761; flag ep5 aligned on the first A, frames 679–718)

### Death (HOLDOUT ep0), frames 722..761

| frame | x | y | air | src | stim_d | theta | dtheta | ttmn | a | a_left | cool_left | enemies (dx,y,type) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 722 | 1174 | 176 | 0 | goomba | 81 | 18.6 | 0.33 | 0.178 | 0 | 0 | 0 | s0:dx+81,y120,t06 |
| 723 | 1176 | 176 | 0 | goomba | 78 | 19.2 | 0.61 | 0.183 | 0 | 0 | 0 | s0:dx+78,y120,t06 |
| 724 | 1178 | 176 | 0 | goomba | 76 | 19.6 | 0.43 | 0.187 | 0 | 0 | 0 | s0:dx+76,y120,t06 |
| 725 | 1179 | 176 | 0 | goomba | 73 | 20.3 | 0.69 | 0.192 | 0 | 0 | 0 | s0:dx+73,y120,t06 |
| 726 | 1181 | 176 | 0 | goomba | 71 | 20.8 | 0.49 | 0.198 | 0 | 0 | 0 | s0:dx+71,y120,t06 |
| 727 | 1183 | 176 | 0 | goomba | 69 | 21.3 | 0.51 | 0.202 | 0 | 0 | 0 | s0:dx+69,y120,t06 |
| 728 | 1185 | 176 | 0 | goomba | 66 | 22.1 | 0.82 | 0.208 | 0 | 0 | 0 | s0:dx+66,y120,t06 |
| 729 | 1186 | 176 | 0 | goomba | 64 | 22.8 | 0.66 | 0.215 | 0 | 0 | 0 | s0:dx+64,y120,t06 |
| 730 | 1188 | 176 | 0 | goomba | 62 | 23.3 | 0.54 | 0.220 | 0 | 0 | 0 | s0:dx+62,y120,t06 |
| 731 | 1190 | 176 | 0 | goomba | 59 | 24.3 | 0.99 | 0.227 | 0 | 0 | 0 | s0:dx+59,y120,t06 |
| 732 | 1192 | 176 | 0 | goomba | 57 | 25.0 | 0.71 | 0.235 | 0 | 0 | 0 | s0:dx+57,y120,t06 |
| 733 | 1193 | 176 | 0 | goomba | 54 | 26.2 | 1.15 | 0.243 | 0 | 0 | 0 | s0:dx+54,y120,t06 s1:dx+98,y56,t06 |
| 734 | 1195 | 176 | 0 | goomba | 52 | 27.0 | 0.83 | 0.252 | 0 | 0 | 0 | s0:dx+52,y120,t06 s1:dx+96,y56,t06 |
| 735 | 1197 | 176 | 0 | goomba | 50 | 27.9 | 0.89 | 0.260 | 0 | 0 | 0 | s0:dx+50,y120,t06 s1:dx+94,y56,t06 |
| 736 | 1199 | 176 | 0 | goomba | 47 | 29.4 | 1.46 | 0.271 | 0 | 0 | 0 | s0:dx+47,y120,t06 s1:dx+91,y56,t06 |
| 737 | 1200 | 176 | 0 | goomba | 45 | 30.6 | 1.18 | 0.282 | 0 | 0 | 0 | s0:dx+45,y120,t06 s1:dx+88,y56,t06 |
| 738 | 1202 | 176 | 0 | goomba | 43 | 31.6 | 1.04 | 0.292 | 0 | 0 | 0 | s0:dx+43,y120,t06 s1:dx+87,y56,t06 |
| 739 | 1204 | 176 | 0 | goomba | 40 | 33.5 | 1.91 | 0.306 | 1 | 17 | 0 | s0:dx+40,y120,t06 s1:dx+84,y56,t06 |
| 740 | 1206 | 176 | 1 | goomba | 38 | 34.9 | 1.42 | 0.321 | 1 | 16 | 0 | s0:dx+38,y120,t06 s1:dx+82,y56,t06 |
| 741 | 1207 | 171 | 1 | goomba | 35 | 37.3 | 2.39 | 0.338 | 1 | 15 | 0 | s0:dx+35,y120,t06 s1:dx+79,y56,t06 |
| 742 | 1209 | 166 | 1 | goomba | 33 | 39.1 | 1.80 | 0.356 | 1 | 14 | 0 | s0:dx+33,y120,t06 s1:dx+77,y56,t06 |
| 743 | 1211 | 162 | 1 | goomba | 31 | 41.1 | 2.00 | 0.374 | 1 | 13 | 0 | s0:dx+31,y120,t06 s1:dx+75,y56,t06 |
| 744 | 1213 | 157 | 1 | goomba | 28 | 44.6 | 3.45 | 0.398 | 1 | 12 | 0 | s0:dx+28,y120,t06 s1:dx+72,y56,t06 |
| 745 | 1214 | 153 | 1 | goomba | 26 | 47.4 | 2.86 | 0.426 | 1 | 11 | 0 | s0:dx+26,y120,t06 s1:dx+69,y56,t06 |
| 746 | 1216 | 149 | 1 | goomba | 24 | 50.3 | 2.86 | 0.452 | 1 | 10 | 0 | s0:dx+24,y120,t06 s1:dx+68,y56,t06 |
| 747 | 1218 | 146 | 1 | goomba | 21 | 55.7 | 5.45 | 0.489 | 1 | 9 | 0 | s0:dx+21,y120,t06 s1:dx+65,y56,t06 |
| 748 | 1220 | 142 | 1 | goomba | 19 | 60.1 | 4.40 | 0.532 | 1 | 8 | 0 | s0:dx+19,y120,t06 s1:dx+63,y56,t06 |
| 749 | 1220 | 139 | 1 | goomba | 16 | 68.3 | 8.18 | 0.587 | 1 | 7 | 0 | s0:dx+16,y120,t06 s1:dx+60,y56,t06 |
| 750 | 1219 | 135 | 1 | goomba | 15 | 71.6 | 3.27 | 0.638 | 1 | 6 | 0 | s0:dx+15,y120,t06 s1:dx+59,y56,t06 |
| 751 | 1218 | 132 | 1 | goomba | 16 | 68.3 | 3.27 | 0.656 | 1 | 5 | 0 | s0:dx+16,y120,t06 s1:dx+60,y56,t06 |
| 752 | 1218 | 130 | 1 | goomba | 16 | 68.3 | 0.00 | 0.651 | 1 | 4 | 0 | s0:dx+16,y120,t06 s1:dx+60,y56,t06 |
| 753 | 1218 | 127 | 1 | goomba | 16 | 68.6 | 0.25 | 0.643 | 1 | 3 | 0 | s0:dx+16,y120,t06 s1:dx+59,y56,t06 |
| 754 | 1218 | 124 | 1 | goomba | 15 | 71.6 | 3.01 | 0.654 | 1 | 2 | 0 | s0:dx+15,y120,t06 s1:dx+59,y56,t06 |
| 755 | 1218 | 122 | 1 | goomba | 14 | 75.2 | 3.61 | 0.681 | 1 | 1 | 0 | s0:dx+14,y120,t06 s1:dx+58,y56,t06 |
| 756 | 1218 | 120 | 1 | goomba | 14 | 75.2 | 0.00 | 0.696 | 1 | 0 | 2 | s0:dx+14,y120,t06 s1:dx+58,y56,t06 |
| 757 | 1218 | 118 | 1 | goomba | 13 | 79.2 | 4.00 | 0.715 | 0 | 0 | 1 | s0:dx+13,y120,t06 s1:dx+57,y56,t06 |
| 758 | 1218 | 116 | 1 | goomba | 12 | 83.6 | 4.45 | 0.751 | 0 | 0 | 0 | s0:dx+12,y120,t06 s1:dx+56,y56,t06 |
| 759 | 1218 | 114 | 1 | goomba | 12 | 83.6 | 0.00 | 0.771 | 1 | 17 | 0 | s0:dx+12,y120,t06 s1:dx+56,y56,t06 |
| 760 | 1219 | 113 | 1 | goomba | 11 | 88.6 | 4.97 | 0.795 | 1 | 16 | 0 | s0:dx+11,y120,t06 s1:dx+55,y56,t06 |
| 761 | 1219 | 113 | 1 | goomba | 10 | 94.5 | 5.88 | 0.842 | 1 | 15 | 0 | s0:dx+10,y120,t06 s1:dx+53,y56,t06 |

### Flag run (HOLDOUT ep5), same position in the jump (first-A aligned), frames 679..718

| frame | x | y | air | src | stim_d | theta | dtheta | ttmn | a | a_left | cool_left | enemies (dx,y,type) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 679 | 1171 | 176 | 0 | goomba | 83 | 18.3 | 0.55 | 0.185 | 0 | 0 | 0 | s0:dx+83,y120,t06 |
| 680 | 1173 | 176 | 0 | goomba | 81 | 18.6 | 0.33 | 0.188 | 0 | 0 | 0 | s0:dx+81,y120,t06 |
| 681 | 1175 | 176 | 0 | goomba | 79 | 19.1 | 0.46 | 0.192 | 0 | 0 | 0 | s0:dx+79,y120,t06 |
| 682 | 1177 | 176 | 0 | goomba | 76 | 19.7 | 0.64 | 0.195 | 0 | 0 | 0 | s0:dx+76,y120,t06 |
| 683 | 1178 | 176 | 0 | goomba | 73 | 20.3 | 0.62 | 0.192 | 0 | 0 | 0 | s0:dx+73,y120,t06 |
| 684 | 1180 | 176 | 0 | goomba | 72 | 20.6 | 0.31 | 0.189 | 0 | 0 | 0 | s0:dx+72,y120,t06 |
| 685 | 1182 | 176 | 0 | goomba | 69 | 21.3 | 0.69 | 0.196 | 0 | 0 | 0 | s0:dx+69,y120,t06 |
| 686 | 1184 | 176 | 0 | goomba | 67 | 21.9 | 0.61 | 0.207 | 0 | 0 | 0 | s0:dx+67,y120,t06 |
| 687 | 1185 | 176 | 0 | goomba | 64 | 22.8 | 0.86 | 0.217 | 0 | 0 | 0 | s0:dx+64,y120,t06 |
| 688 | 1187 | 176 | 0 | goomba | 62 | 23.3 | 0.54 | 0.229 | 0 | 0 | 0 | s0:dx+62,y120,t06 |
| 689 | 1189 | 176 | 0 | goomba | 60 | 24.1 | 0.73 | 0.239 | 0 | 0 | 0 | s0:dx+60,y120,t06 |
| 690 | 1191 | 176 | 0 | goomba | 57 | 25.1 | 1.05 | 0.242 | 0 | 0 | 0 | s0:dx+57,y120,t06 s1:dx+100,y56,t06 |
| 691 | 1192 | 176 | 0 | goomba | 54 | 26.2 | 1.06 | 0.244 | 0 | 0 | 0 | s0:dx+54,y120,t06 s1:dx+98,y56,t06 |
| 692 | 1194 | 176 | 0 | goomba | 53 | 26.7 | 0.51 | 0.250 | 0 | 0 | 0 | s0:dx+53,y120,t06 s1:dx+96,y56,t06 |
| 693 | 1196 | 176 | 0 | goomba | 50 | 27.9 | 1.22 | 0.260 | 0 | 0 | 0 | s0:dx+50,y120,t06 s1:dx+94,y56,t06 |
| 694 | 1198 | 176 | 0 | goomba | 48 | 29.0 | 1.06 | 0.276 | 0 | 0 | 0 | s0:dx+48,y120,t06 s1:dx+91,y56,t06 |
| 695 | 1199 | 176 | 0 | goomba | 45 | 30.6 | 1.58 | 0.294 | 0 | 0 | 0 | s0:dx+45,y120,t06 s1:dx+88,y56,t06 |
| 696 | 1201 | 176 | 0 | goomba | 43 | 31.6 | 1.04 | 0.308 | 1 | 17 | 0 | s0:dx+43,y120,t06 s1:dx+87,y56,t06 |
| 697 | 1203 | 176 | 1 | goomba | 41 | 33.0 | 1.38 | 0.318 | 1 | 16 | 0 | s0:dx+41,y120,t06 s1:dx+84,y56,t06 |
| 698 | 1205 | 171 | 1 | goomba | 38 | 35.1 | 2.10 | 0.326 | 1 | 15 | 0 | s0:dx+38,y120,t06 s1:dx+81,y56,t06 |
| 699 | 1206 | 166 | 1 | goomba | 35 | 37.3 | 2.26 | 0.342 | 1 | 14 | 0 | s0:dx+35,y120,t06 s1:dx+79,y56,t06 |
| 700 | 1208 | 162 | 1 | goomba | 34 | 38.3 | 1.03 | 0.360 | 1 | 13 | 0 | s0:dx+34,y120,t06 s1:dx+77,y56,t06 |
| 701 | 1210 | 157 | 1 | goomba | 31 | 41.1 | 2.77 | 0.372 | 1 | 12 | 0 | s0:dx+31,y120,t06 s1:dx+75,y56,t06 |
| 702 | 1212 | 153 | 1 | goomba | 29 | 43.5 | 2.41 | 0.390 | 1 | 11 | 0 | s0:dx+29,y120,t06 s1:dx+72,y56,t06 |
| 703 | 1213 | 149 | 1 | goomba | 26 | 47.4 | 3.91 | 0.421 | 1 | 10 | 0 | s0:dx+26,y120,t06 s1:dx+69,y56,t06 |
| 704 | 1215 | 146 | 1 | goomba | 24 | 50.3 | 2.86 | 0.437 | 1 | 9 | 0 | s0:dx+24,y120,t06 s1:dx+68,y56,t06 |
| 705 | 1217 | 142 | 1 | goomba | 22 | 54.0 | 3.71 | 0.452 | 1 | 8 | 0 | s0:dx+22,y120,t06 s1:dx+65,y56,t06 |
| 706 | 1218 | 139 | 1 | goomba | 19 | 60.4 | 6.37 | 0.505 | 1 | 7 | 0 | s0:dx+19,y120,t06 s1:dx+62,y56,t06 |
| 707 | 1218 | 135 | 1 | goomba | 17 | 65.3 | 4.97 | 0.580 | 1 | 6 | 0 | s0:dx+17,y120,t06 s1:dx+61,y56,t06 |
| 708 | 1218 | 132 | 1 | goomba | 17 | 65.6 | 0.25 | 0.625 | 1 | 5 | 0 | s0:dx+17,y120,t06 s1:dx+60,y56,t06 |
| 709 | 1218 | 130 | 1 | goomba | 16 | 68.3 | 2.73 | 0.628 | 1 | 4 | 0 | s0:dx+16,y120,t06 s1:dx+60,y56,t06 |
| 710 | 1218 | 127 | 1 | goomba | 16 | 68.6 | 0.25 | 0.635 | 1 | 3 | 0 | s0:dx+16,y120,t06 s1:dx+59,y56,t06 |
| 711 | 1218 | 124 | 1 | goomba | 15 | 71.9 | 3.28 | 0.657 | 1 | 2 | 0 | s0:dx+15,y120,t06 s1:dx+58,y56,t06 |
| 712 | 1218 | 122 | 1 | goomba | 14 | 75.2 | 3.34 | 0.690 | 1 | 1 | 0 | s0:dx+14,y120,t06 s1:dx+58,y56,t06 |
| 713 | 1218 | 120 | 1 | goomba | 14 | 75.5 | 0.27 | 0.708 | 1 | 0 | 2 | s0:dx+14,y120,t06 s1:dx+57,y56,t06 |
| 714 | 1218 | 118 | 1 | goomba | 13 | 79.5 | 4.01 | 0.718 | 0 | 0 | 1 | s0:dx+13,y120,t06 s1:dx+56,y56,t06 |
| 715 | 1218 | 116 | 1 | goomba | 12 | 83.6 | 4.17 | 0.766 | 0 | 0 | 0 | s0:dx+12,y120,t06 s1:dx+56,y56,t06 |
| 716 | 1218 | 114 | 1 | goomba | 12 | 83.9 | 0.29 | 0.792 | 1 | 17 | 0 | s0:dx+12,y120,t06 s1:dx+55,y56,t06 |
| 717 | 1218 | 113 | 1 | goomba | 11 | 88.6 | 4.67 | 0.805 | 1 | 16 | 0 | s0:dx+11,y120,t06 s1:dx+55,y56,t06 |
| 718 | 1219 | 113 | 1 | goomba | 11 | 88.9 | 0.30 | 0.807 | 1 | 15 | 0 | s0:dx+11,y120,t06 s1:dx+54,y56,t06 |


## 4. Classification against the pre-registered criteria

| class | criterion | result |
|---|---|---|
| HOLD_COOLDOWN | TTMn ≥ threshold while hold/cooldown blocked a new A in the 30 frames before contact | **Literally met**: frames 757–758 are refused (a=0, cooldown_left 1→0) with TTMn 0.715 / 0.751 ≥ 0.2953. But the **same 2-frame refusal happens in the flag run** (frames 714–715, TTMn ≥ thr) with the same y arc. It is the fixed 18-frame hold + 2-frame cooldown cycle present in every jump, so it does not distinguish death from survival |
| LATE_TRIGGER | first A at stim_d < 16, or none while not blocked | No: first A at 40 px (flag run 43 px); nothing blocked it |
| EARLY_TRIGGER | A starts at stim_d > 60 and Mario lands before passing | No: 40 px |
| LANDING | A in 16–60 px but Mario comes down on/into the Goomba (air→ground within 8 px) | Not met: Mario never touches ground; he is hit in the air (air=1 at the last frame) at the apex |
| OTHER | – | **Chosen.** A normal-window trigger, an apex of y=113 at a ledge whose Goomba stands at the same height, in a place where the circuit has no ledge percept |

**2-Goomba group?** Yes. s0 (on the lower row) is at dx +10 at the death; s1 is on the upper row at dx +53 (y 56, not falling yet) and was already visible 6 frames before the first A (frame 733). In the flag run s1 later walks off its row and drops to y 120 (frames 723→745). s1 did not arrive during the hold/cooldown window and did not cause this death (s0 did), but both feed the `sum` stimulus, so θ is the sum of the two objects.

**Flag run versus death at the same x:** see section 2: the same arc, a first A 3 px earlier (x 1201 vs 1204), and a Goomba 1 px further away at t=22; the flag run's later flight is the same 18-frame hold, 2-frame cooldown pattern repeated all the way to the flag (it then needs many more jumps, so one pass here does not make the run robust).

## 5. Decision

- **OTHER → stop and report** (the pre-registered rule). I did not start 7c/7d and changed no knob.
- For your call, the other readings: **HOLD_COOLDOWN read literally** (criterion met) or **LANDING read loosely** ("contact after a normal-window A") would both give *no new knob, skip 7c, go to 7d*. LATE/EARLY (→ add LPLC2_GAIN + LC4_GAIN) are not supported by anything here: the trigger is at 40 px, not <16 or >60.
- Two things you may want to weigh before 7c/7d, neither tested here (no knob change was allowed): (1) the apex (y 113) misses the ledge-top height (112) by 1 px, so the existing knobs `A_HOLD` (range 4–32; r3 uses 18) and `COOLDOWN` plausibly are the levers; a hypothesis, not a result. (2) The ledge being invisible to the circuit is a stimulus-layer gap (`level.SOLID_WALL`), outside the 7a scope ("nothing in senses changes") and, per CLAUDE.md, anything there needs the shadow-run re-analysis; I did not touch it.
- Caveat on the evidence: one flag run (σ0.05) versus 9 non-flags, and 7 of the 8 ledge deaths are replicas of one deterministic trajectory (ep7 differs by 1 px; Part 6b counted 4 distinct trajectories of 10).
