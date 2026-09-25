# 033 -- win log (win_attempt, 1-1, sigma=0, seed=0, max_frames 4000)

One row per iteration. Loop: run headless, diagnose the 60 frames before death, smallest fix for that one cause.

| iter | death x / cause | fix | new max_x |
|---:|---|---|---:|
| 0 | 1430 -- same 3-tile pit; SPEC_pits override fired mid-air, A held through the landing, no takeoff | `grounded_pit` module: fire only when RAM 0x001D == 0 with A up on the previous frame (also ADDR_ENEMY_Y -> 0x00CF, goldens held) | 1430 |
| 1 | 1520 -- Goomba; escape hop blocked by the 40-frame cooldown that follows the long pit jump (TTMn already 19-22, threshold 3) | `threat_bypass` module: lift only the cooldown for a grounded threat within 40 px ahead | 1520 |
| 2 | ~1782 -- Goomba across a page boundary: its x byte (1) minus Mario's (242) read as ~230 px behind, so looming stayed silent until the jump fired at 13 px, too late | `page_threat` module: page-corrected distance (RAM 0x006E+slot), short hop through DNp01 within 40 px | 1782 |
| 3 | none -- **flag reached**, frame 2148, x=3157, score 1500 | -- | 3157 |

Iterations were run with a direct FullPolicy diagnostic loop (headless, telemetry-level detail) rather than one run_one per iteration; the final run went through `tool.core.runner.run_one` (033_first_win).
