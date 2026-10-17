# 001 senses: pipe + pit (flyrun, part 2 of 6)

Videos: `001_all_on.mp4` (fly only, everything on) and `001b_pit_assisted.mp4` (ASSISTED, see pit A/B). Raw numbers: `001_test_numbers.json`. Per-frame logs: `001_all_on_log.csv`, `001b_pit_assisted_log.csv`. Tests: 10/10 pass (6 from part 1, 4 new).

## Decoder (level.py)

NES tile buffer: `0x0500 + 208*page + 16*row + col`, 13 rows x 16 cols, world page P is stored in buffer page P%2. Found by dumping the buffer at pipe 1: 0 = sky, 84 = ground (rows 11-12), 18/19/20/21 = pipe, 81/192/193 = brick / ?-block, 97 = hard stair block (not seen in a dump; it is the standard SMB stair tile, included on trust and consistent with the stair walls below). A pit is a column with both ground rows empty. Lookahead is limited to the visible screen (`ScreenLeft + 256`), because the buffer holds stale pages beyond it.

## Level map (`001_level_map.csv`; scripted scroll reached x = 2180, so coverage ends at the stairs)

| kind | x | size (px) | | kind | x | size (px) |
|---|---|---|---|---|---|---|
| pipe 1 | 448 | H 32 | | pit 1 | 1104 | W 32 |
| pipe 2 | 608 | H 48 | | pit 2 | 1376 | W 48 |
| pipe 3 | 736 | H 64 | | stairs up | 2144 / 2160 / 2176 / 2192 | H 16 / 32 / 48 / 64 |
| pipe 4 | 912 | H 48 | | stairs down | 2240 / 2256 / 2272 / 2288 | H 64 / 48 / 32 / 16 |

Pipe 1 and pit 1 match the notebooks (448 / H 32, 1104 / W 32). Later parts of the level (past x about 2450) were not reached by the scripted scroll.

## Motor: MUSCLE_DECAY failed, A_HOLD + COOLDOWN kept

MUSCLE_DECAY (trace = max(TTMn, trace x decay), A while trace >= thresh) at decay 0.8 / 0.9 / 0.95: stuck at pipe 1 in all three (x 434), A_frac 0.45 / 0.46 / 0.50, longest A run 165 frames. The result does not depend on the decay value. TTMn keeps rising as the face nears, so the trace never falls below threshold and A is never released; SMB needs A released to start a new jump. So the trace cannot work in this circuit, and A_HOLD + COOLDOWN (nb 14) is kept; `MUSCLE_DECAY` was removed from knobs.

A_HOLD / COOLDOWN values tried (nb 14 and nb 15 values only, fly only, all senses on): 12/0 reaches x 706, longest A run 48 (over the limit of 40); 12/10 reaches x 687, longest run 12; 20/15 reaches x 708, longest run 20; 24/10 reaches x 708, longest run 24. Default set to 12 / 10 (nb 14 hold, nb 14 cooldown), the cleanest of the four on the no-flood criterion.

## A/B table

| Test | Setting | max_x | end_reason | x_at_end | first A (d, px) | A_frac | longest A run |
|---|---|---|---|---|---|---|---|
| pipe | PIPE_SENSE off | 435 | stuck | 434 | none | 0.03 | 12 |
| pipe | PIPE_SENSE on | 687 | died | 687 | pipe 1: d = 40 (x 410), theta 43.6 deg | 0.21 | 12 |
| pit (assisted) | PIT_SENSE off | 1138 | died | 1138 | none | n/a | n/a |
| pit (assisted) | PIT_SENSE on | 2226 | stuck | 2226 | pit 1: d = 39 (x 1066), theta 44.6 deg | n/a | n/a |

Pipe on: cleared pipe 1 (max_x > 479): yes. It did not need a retrigger: the second A at pipe 1 (x 448, d = 1) is the jump that gets over after the first one landed on the near side.

Pit A/B is ASSISTED: the fly cannot reach the pit alone (dies at x 687), so a scripted driver (`scripted.py`, disclosed in the `driver` column) plays to x >= 1037 on the ground, the nb 15 takeover point, and the fly takes over from a silent brain (takeover at x 1038). Off: walks in and dies at the first pit (x 1138). On: crosses pit 1 and pit 2, then ends stuck at x 2226 at the stairs (stairs are walls of 16-64 px that rise one tile per column; they were not designed for here).

Jump length vs pit width: the pit-1 crossing is an air stretch from x 1068 to 1122 (54 px of Mario-x travel in the air, and the second A press at x 1105 adds to it) against W = 32, so a walking jump is long enough for pit 1 with margin. Pit 2 (W 48): air stretch 1357 to 1411 (54 px) and it was cleared. The air stretch ends with Mario's left edge still above the pit, so these numbers are lower bounds on the take-off-to-landing distance.

## Death map (default run, everything on, fly only; `001_all_on.mp4`)

| x | what stopped or killed him | why |
|---|---|---|
| 289 | cleared Goomba #1 | first A at d = 20 px, theta 43.6 deg, same as part 1 |
| 410 to 448 | cleared pipe 1 | first A at d = 40, the jump lands short of the face, the second A at d = 1 gets over |
| 550 to 602 | cleared pipe 2 (H 48) | four A onsets (d = 60, 21, 14, 7): the early jump lands before the face, the later ones get over at x about 602 |
| 687 | killed by Goomba, 8 px ahead of him | the pipe 3 face (H 64) wins the single channel with theta 0.76 to 1.07 rad at d 80 to 54, so the Goomba (theta smaller than the pipe's until d is about 11) is masked. The pipe-triggered A at d = 80 (x 658) started a 12-frame hold plus 10-frame cooldown, so when the Goomba arrived the cooldown blocked the jump. 28 of the last 30 frames name the pipe as the source |

## Surprising

1. `noop_start` is a pure time shift: values 0, 6, ..., 60 all give max_x 687 and the same death, only `frames` shifts. It will not give different episodes in later parts unless something else varies.
2. The single-channel max hides threats: a tall pipe outranks a nearby Goomba, and the cooldown then blocks the escape.
3. The first A always fires at theta 43.6 deg (0.761 rad) whatever the source (Goomba d = 20, pipe 1 d = 40, pipe 2 d = 60, pipe 3 d = 80): TTMn crosses 0.10 at the same theta, so the trigger distance scales with face height.
