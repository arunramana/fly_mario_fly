# 032 -- graded pit response (`projects/win_attempt/runs/032_graded_pits.mp4`)

**Setup.** `win_attempt`, 1-1, sigma=0, seed=0, max_frames=3000, `inject_gap_frame` cleared, `scenario.graded_pit_response=True` (docs/SPEC_pits.md: cooldown override near a pit, long jump by distance to the edge, B held for a run-up; controller scaffolding, not circuit behaviour). Brain panel on.

**What happened.** 1023 frames, died, max_x_abs=1430, score=300, 14 escape jumps (4 long). The 3-tile pit that killed the flag-off run at frame 689 (x=1432) is cleared; the run then dies to enemy contact with no pit in the final frames. Telemetry: `projects/win_attempt/telemetry/032_graded_pit_validation_telemetry.csv`.

**What we learned.** Better on the pit, not on the outcome: it lasts 334 frames longer but reaches the same peak x. Telemetry CSV is the record; the video is ephemeral.
