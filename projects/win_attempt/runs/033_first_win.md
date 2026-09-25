# 033 -- first 1-1 win (`projects/win_attempt/runs/033_first_win.mp4`)

**Setup.** `win_attempt`, 1-1, sigma=0, seed=0, max_frames 4000. Controller modules on in the config (all SCAFFOLDING, see each class's docstring in `bridge/controller_modules.py`): `grounded_pit` (ground-aware, fresh-A pit jump + B run-up), `threat_bypass` (lift the jump cooldown for a grounded threat within 40 px), `page_threat` (page-corrected enemy distance, short hop within 40 px). `graded_pit_response` off. ENEMY_Y address corrected to 0x00CF.

**What happened.** Flag reached at frame 2148, max_x 3157, score 1500, time left 296. Three fixes from three deaths (pit x=1430, Goomba x=1520, Goomba x~1782); see `033_win_log.md`.

**What we learned.** Every failure was a mechanical gate or a perception gap, not a circuit one: a mid-air commit, a cooldown outliving its purpose, and an enemy distance that ignored the page byte. All three fixes are hand-placed controller rules, none is claimed as fly circuit behaviour. Telemetry: `projects/win_attempt/telemetry/033_first_win_telemetry.csv`.
