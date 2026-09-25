# 032 -- graded pit response (`projects/win_attempt/runs/032_graded_pits.mp4`)

**Setup.** `win_attempt`, 1-1, sigma=0, seed=0, max_frames=3000, `inject_gap_frame` cleared, `scenario.graded_pit_response=True` (docs/SPEC_pits.md: cooldown override near a pit, long jump by distance to the edge, B held for a run-up; controller scaffolding, not circuit behaviour). Brain panel on.

**What happened.** 1023 frames, died, max_x_abs=1430, score=300, 14 escape jumps (4 long). The commit now fires before the timer would have reopened, but it does not clear the pit; the run then dies at the SAME pit at frame 1023 (y rises 176->253, i.e. falling; both Goombas are behind Mario) -- corrected from an earlier 'enemy' call. The override commit fired mid-air, so A was held through the landing and never produced a takeoff before the edge. Telemetry: `projects/win_attempt/telemetry/032_graded_pit_validation_telemetry.csv`.

**What we learned.** It lasts 334 frames longer (one more attempt) but the pit still kills. Telemetry CSV is the record; the video is ephemeral.
