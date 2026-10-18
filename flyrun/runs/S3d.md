# S3d: tower anchored to the pit's highest rim (senses v2 + motor v2, default knobs, no tuning, no new knobs; base f90a141)

**Result: the smoke run (noop 0, sigma 0) reaches the flag. The HOLDOUT does not: real wiring 0/10, theta-rule 8/10.** No rule changed after seeing either.

## 0. Spec
`flyrun/SPEC.md` B9: tower base = the highest surrounding ground of the pit (the top of the solid column at the near edge / far edge), top = that - min(W, 68), never anchored to the floor; S3c note added.

## 1. Implementation + tests
- `senses_v2.rim_top(walls, x)`: top y of the wall column at x (else the floor, 176). Near rim = the column just before the pit, far rim = the column at the far edge. Tower top = min(near_y, far_y) - min(W, 68). The tower stays on the far edge, still released-until-landing; the base is unchanged. Rims are carried in the threat's `extra` for the overlay (cyan lines over both rim columns).
- Tests (`test_senses_v2.py`, 24 pass; full flyrun suite: see commit):
  - Pit 3 from the top step (feet 112, W 32): tower top 80, h 32; the trigger fires **8 px** before the near edge (0.25 W + 8 = 16, within +-12).
  - Synthetic pit, far rim 32 px high: rims (176, 144), tower top 112 = 144 - 32, measured from the far rim; with the near rim higher it is measured from the near rim; with no raised rim the tower top is 176 - 32 (pits 1 and 2 as S3c).
  - Pits 1 and 2 unchanged in the run: take-offs 6 and 11 px, same as S3c (0 px difference).
  - Changed expectations: none; two new tests plus the pit-3 helper constant.

## 2. Smoke (noop 0, sigma 0, unassisted): `runs/S3d_smoke_log.csv`, `runs/S3d_jumps.csv`, `runs/S3d_full_run.csv`
**Flag**, max_x 3161, 1951 frames, A fraction 0.30, 2 blind presses, 0 Left presses.
| pit | W | jumps | take-off (front edge -> near edge) | 0.25 W + 8 | landing x |
|---|---|---|---|---|---|
| 1 (1104) | 32 | 1 | 6 px | 16 | 1164 |
| 2 (1376) | 48 | 1 | 11 px | 20 | 1436 |
| 3 (2448) | 32 | 1 (from the top step, after a separate stair jump at 2402) | 6 px | 16 | 2518 |
Pit 3, which killed S3c, is now crossed in one jump. Pipe 4 (jumps only, no fix): jump 1 at frame 486 from x 830 (A 41 frames, lands x 899 at the foot), jump 2 at frame 541 from x 898 (A 27, lands on top x 900); unchanged since S3b.

## 3. HOLDOUT (Part 6b list, 10 episodes), real wiring and theta-rule (trigger 43.6 deg, remeasured: median of 81 onsets, range 41.1-50.4)
Real wiring:
| noop | seed | sigma | flag | max_x | end (x, cause) | blind | Left presses | A frac |
|---|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.25 |
| 11 | 102 | 0.0 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.25 |
| 25 | 103 | 0.0 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.24 |
| 33 | 104 | 0.0 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.24 |
| 41 | 105 | 0.0 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.24 |
| 3 | 101 | 0.05 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.25 |
| 11 | 102 | 0.05 | no | 1415 | died (1415, pit) | 2 | 0 | 0.22 |
| 25 | 103 | 0.05 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.24 |
| 33 | 104 | 0.05 | no | 1804 | died (1804, enemy dx=-18) | 2 | 0 | 0.24 |
| 41 | 105 | 0.05 | no | 2474 | died (2474, pit) | 2 | 0 | 0.26 |

theta-rule:
| noop | seed | sigma | flag | max_x | end (x, cause) | blind | Left presses | A frac |
|---|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 11 | 102 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 25 | 103 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 33 | 104 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 41 | 105 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 3 | 101 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 11 | 102 | 0.05 | no | 1127 | died (1127, pit) | 2 | 0 | 0.19 |
| 25 | 103 | 0.05 | no | 1127 | died (1127, pit) | 2 | 0 | 0.19 |
| 33 | 104 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |
| 41 | 105 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |

| arm | flags | mean max_x | distinct (max_x, death x) | distinct (x, A) traces | blind presses (total) | Left presses | silence A_frac |
|---|---|---|---|---|---|---|---|
| real | 0/10 | 1832 | 3 | 10 | 20 | 0 | 0.00 |
| theta-rule | 8/10 | 2754 | 2 | 10 | 20 | 0 | 0.00 |

- **The real fly dies at x 1804 in 8 of 10 episodes** (cause label "enemy dx=-18": a Goomba pair around x 1790-1810; all five sigma-0 episodes and three of five sigma-0.05). In the trace (`runs/S3d_holdout_3_0.0.csv`) he takes off at 1769, 18 px from the first Goomba, theta 43.6, and the jump peaks only 34 px up (feet 142; a full jump is 68), A is released early, he comes down on the pair at x 1804. The smoke run (noop 0) does not die here; I did not check why (the start timing shifts where the Goombas are relative to him, which is my guess, not verified).
- The two other deaths are pits at sigma 0.05: pit 2 at x 1415 (noop 11; the pit-2 jump falls ~10 px short) and pit 3 at x 2474 (noop 41).
- The theta-rule, with the same senses and a pure theta >= 43.6 deg trigger/hold, passes the 1804 Goombas in all 8 episodes that reach them and flags 8/10; its two deaths are pit 1 at x 1127 (sigma 0.05, noop 11 and 25).
- Traces: `runs/S3d_holdout_<noop>_<sigma>.csv` (real fly), `runs/S3d_holdout_theta_rule_<noop>_<sigma>.csv` (theta-rule), same columns as S3c.

## Reading
(a) The win is not robust on HOLDOUT: 0/10 for the real wiring, with 8 of the 10 deaths at the same spot (the Goomba pair near x 1804), while the single smoke episode flags. (b) On this data the theta-rule does better than the real wiring (8/10 vs 0/10) with identical senses and motor: the wiring is not what clears this level; at x 1804 the real fly's jump is shorter than the rule's. I did not diagnose why beyond the trace above; shuffles and the blind timer were not rerun (not asked).

## 4. Saved
`clips/S3d_full_run.mp4` (gitignored): the whole smoke episode, 1951 frames = 32.5 s at 1x, with the overlay (tower magenta, base orange, both rim heights cyan). `runs/S3d_full_run.csv`: same columns as S3c.
