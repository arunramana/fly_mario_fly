# S3e: cleared enemies hand over to the next threat (senses v2 + motor v2, default knobs, no tuning, no new knobs; base 970c973)

**Result: smoke run reaches the flag (3161). HOLDOUT: real wiring 9/10 flags, theta-rule 8/10.** The x 1804 Goomba-pair deaths of S3d are gone. No rule changed after seeing the results.

## 0. Spec
`flyrun/SPEC.md`, "Threat choice (S3e)": the cleared-enemy rule and the S3d note, as given.

## 1. Implementation + tests
- `senses_v2.is_cleared(mx, feet, enemy)`: feet at/above the enemy's top AND his body over it (the pipe-face / tower test). `choose(..., cleared=)` skips enemies that are cleared this frame or in `cleared`; `SensesV2` accumulates the idents cleared while airborne and empties the set on landing (ram 0x001D == 0). dtheta resets to 0 at the switch (unchanged mechanism: new identity).
- Tests (`test_senses_v2.py`, 27 pass; full flyrun suite: 78 pass):
  - Pair 24 px apart: grounded / rising below G1's top -> G1; feet above G1's top but not yet over it -> G1; feet above AND over -> G2; a single cleared Goomba -> nothing ahead.
  - Stateful: once cleared, G1 stays dropped while he falls below its top still over it; landing empties the set; a single Goomba behaves as before; dtheta == 0 at the G1 -> G2 switch.
  - Pipes, pits, and every earlier test unchanged and passing. Changed expectations: none.
- **The S3d oddity (theta-rule, noop 11, sigma 0, from frame 1109 x 1803, threat "none").** Replayed with RAM: at frame 1109 Goomba 2 (slot 1, at x 1810) had RAM state 4 = stomped (he came down on it at frame ~1106-1109, feet 159-161), so it is correctly ignored; Goomba 1 (slot 0, x 1784) was 19 px BEHIND him, so also ignored (threats behind are ignored, as designed). Nothing live ahead -> none. The trace was right; he had jumped Goomba 1 and stomped Goomba 2.

## 2. Smoke (noop 0, sigma 0, unassisted): `runs/S3e_smoke_log.csv`, `runs/S3e_jumps.csv`, `runs/S3e_full_run.csv`
**Flag**, max_x 3161, 1947 frames, A fraction 0.28, 2 blind presses, 0 Left presses. Pits as before: 1 jump each (take-off 6 / 10 / 6 px, landing 1165 / 1436 / 2518); pipe 4 unchanged (2 jumps).
The pair (jump from x 1767, frame 1062):
- Frames 1062-1071: A down (about 10 frames), threat G1 (box x 1792), theta rising to 86 deg.
- **Frame 1071 (x 1782, feet 142): the box switches to G2 (x 1815)**: feet above G1's top (160) and his body over it. theta falls 59 -> 31 deg, TTMn 0.18 -> 0.13.
- Frame 1072: TTMn 0.088 < 0.10, **A released** (loom faded) with the feet at y 139. He stays in the air about 43 more frames.
- Frames 1079-1090: he comes down on G2 (feet 160 at 1083), G2's box disappears at frame 1091 (stomped), then the threat is none; **lands at frame 1115, x 1833, survived** (the jump table: "landed on enemy (stomped)").

## 3. HOLDOUT (Part 6b list), trigger 43.6 deg (remeasured: median of 167 onsets, range 40.0-97.6, the top end is higher than in S3d (50.4 in S3d; not investigated); the median is unchanged)
Real wiring:
| noop | seed | sigma | flag | max_x | end (x, cause) | blind | Left presses | A frac |
|---|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 11 | 102 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 25 | 103 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 33 | 104 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 41 | 105 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 3 | 101 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 11 | 102 | 0.05 | no | 1128 | died (1128, pit) | 2 | 0 | 0.22 |
| 25 | 103 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 33 | 104 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.27 |
| 41 | 105 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |

theta-rule:
| noop | seed | sigma | flag | max_x | end (x, cause) | blind | Left presses | A frac |
|---|---|---|---|---|---|---|---|---|
| 3 | 101 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 11 | 102 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.26 |
| 25 | 103 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |
| 33 | 104 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |
| 41 | 105 | 0.0 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |
| 3 | 101 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.28 |
| 11 | 102 | 0.05 | no | 1418 | died (1418, pit) | 2 | 0 | 0.20 |
| 25 | 103 | 0.05 | no | 1410 | died (1410, pit) | 2 | 0 | 0.20 |
| 33 | 104 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.24 |
| 41 | 105 | 0.05 | yes | 3161 | flag (3161, flag) | 2 | 0 | 0.25 |

| arm | flags | mean max_x | distinct (max_x, death x) | distinct (x, A) traces | blind (total) | Left presses | silence A_frac |
|---|---|---|---|---|---|---|---|
| real | 9/10 | 2958 | 2 | 10 | 20 | 0 | 0.00 |
| theta-rule | 8/10 | 2812 | 3 | 10 | 20 | 0 | 0.00 |

Deaths: real - one, noop 11 sigma 0.05, **pit 1 at x 1128**. theta-rule - two, sigma 0.05, noop 11 and 25, **pit 2 at x 1418 / 1410**. Before S3e the real fly was 0/10 with 8 deaths at the Goomba pair (x 1804); there are none now.

## Reading
(a) The win is much more robust than in S3d: 9/10 on HOLDOUT, the one failure is a sigma 0.05 pit-1 jump. (b) The theta-rule (same senses, same motor, trigger = the fly's measured trigger angle) is nearly as good (8/10), so on this HOLDOUT the real wiring is at most one episode ahead of a threshold rule: no evidence here that the connectome does something the rule does not. (Shuffles and the blind timer were not rerun.) Caveat: 10 episodes, 5 start timings x 2 sigmas; the sigma-0 half is deterministic per start timing.

## 4. Saved
`clips/S3e_full_run.mp4` (gitignored): smoke run, 1947 frames = 32.5 s at 1x, overlay with the threat box (G2's box is drawn from frame 1071). `clips/S3e_pair.mp4`: 3.2 s at 0.5x of the pair in HOLDOUT noop 11, sigma 0 (this episode now FLAGS; in S3d it died there). `runs/S3e_full_run.csv`, `runs/S3e_holdout_*.csv` (real) and `runs/S3e_holdout_theta_rule_*.csv`, S3d columns.
