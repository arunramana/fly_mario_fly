# 007 — terrain: pits, graded takeoff, and speed

Tile RAM decoder (`tile_ram.py`) added, verified against the real
disassembly source and cross-checked frame-by-frame against captured
screenshots (ground=`0x54`, `?`-blocks=`0xC0`/`0xC1` at row 11/rows 0-12 of
`Block_Buffer_1`/`_2`, not the `0xC2`/`0xC3` originally guessed). A real
1-1 pit (2 tiles wide, frame ~476) drove DNp01 via `GAP_GAIN=0.6`, which
recruited DLMn through the real DNp01->GFC1-4->DLMn relay (verified: zero
direct DNp01->DLMn synapses, 80 real edges via GFC1-4) past
`DLMN_RECRUIT_THRESHOLD=1.0`, triggering the graded long jump
(`LONG_JUMP_HOLD_FRAMES=35` vs the normal 25) — the pit was cleared. DNp09
(`speed_circuit.py`, 25 neurons, `WALK_DRIVE=1.0`/`G_SPEED=1.2`) now gates
B instead of holding it permanently; visible in the telemetry as B
releasing during every jump/climb-stall and a brief hesitant
walk-pause-walk chatter right after each one clears, rather than an
instant resume.

Died at frame 565 to what looks like an ordinary Goomba encounter
(LPLC2/DNp01 elevated at death, DLMn back at 0) — unrelated to the new
terrain circuits, which had already done their job earlier in the run.
Items 4/5 (`?`-block odour + hunger gating) were **not** attempted this
sprint — 1-3 alone left no comfortable room to spare, per the sprint's own
triage ("ship 1+2+3... leave 4+5 for next sprint if it runs long").
