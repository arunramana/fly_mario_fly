Sprint 026: brain_panel speed + layout, no behaviour change. Profiled
first -- 8.4ms/frame (worst case) against a 16.7ms budget, already
under; the one real waste was `_font()` reloading TTF files every
frame (fixed, cached, ~2.7ms saved). Per the sprint's own rule ("if
under budget, stop"), no GPU port attempted.

New layout, 1536x1080: left 512px is the brain silhouette (upper 2/3,
nothing overlaid -- spikes/glow only) over a dedicated telemetry strip
(lower 1/3, every banner/legend/readout that used to sit on the brain).
Right 1024px: emulator at integer 4x, nearest-neighbour, vertically
centred. Re-profiled after: 5.8ms/frame, still well under budget.

This video reproduces 017's exact scenario (same seed/level/params,
807 frames, event-for-event identical) with the new panel, so it's
directly comparable to runs/017_step1_fixes.mp4. See docs/RUNS.md 026.
