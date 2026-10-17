# 000 scaffold (flyrun, part 1 of 6)

Network: `tutorials/_cache/W_steer.npy`, 636 neurons. Knobs are all defaults from `flyrun/knobs.py`. Video: `000_default.mp4`. Raw numbers: `000_test_numbers.json`.

## Type counts (all required types present)

| LC4 L/R | LPLC2 L/R | DNp01 | TTMn | DNp09 | LC10a L/R | DNa (01+02) L/R |
|---|---|---|---|---|---|---|
| 71 / 55 | 94 / 91 | 2 | 2 | 2 | 135 / 140 | 2 / 2 |

## Tests 2-6

| Test | Result | Numbers |
|---|---|---|
| 2 silence (HOME_R=0, no enemy input) | pass | max_x 40, 0 A presses, ended "stuck" at frame 151 |
| 3 homing (HOME_R=0.5) | pass | max_x 435, Right pressed 100% of frames, ended "stuck" |
| 4 telemetry | pass | all 13 columns present, no NaN in x / ttmn / buttons |
| 5 determinism | pass | same knobs and noop_start=0 twice: max_x 435 and 435, identical x trace. noop_start 17 vs 0: x trace differs; max_x is still 435 |
| 6 parity (report only) | recorded | first A at frame 155: d = 20 px, theta = 43.6 deg, tau = 10 frames. Goomba #1 passed (alive past x=340) |

Parity vs NOTES.md (d about 20-24, theta about 37-44 deg, tau about 10-12): inside the band on all three. As NOTES says, tau is late against the human 30-45 frames.

## Where and why he stops

A default run walks Right the whole way, jumps over Goomba #1 at d = 20 px (score stays 0, so jumped over, not stomped), then ends "stuck" at x = 434 against pipe 1 (face at x = 448). Part 1 has no pipe sense, so nothing triggers a jump and Mario holds Right into the pipe for 150 frames.
