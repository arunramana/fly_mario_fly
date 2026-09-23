Sprint 024, second and final retinotopy attempt. Fixed 023's actual bug:
the foveal origin was `hex1.min()` (the sparsest edge of each real
RF-centre distribution); moved it to `retinotopy.density_mode()`, the
real measured density peak (LC4/LPLC2, L/R, all four modes land near
the middle of their own range, not at an edge). Weight-at-origin rose
4.4x (0.05 -> 0.22) exactly as predicted. Still 0 escape commitments,
still died at frame 170 -- the EXACT same frame as 023, frame-for-frame
identical trajectory. The recurrent circuit needs something close to
the old uniform population engagement to reach threshold; no single-
target Gaussian tuning curve supplies that, wherever its centre sits.
Hard stop, as pre-registered: retinotopy is closed permanently.
`retinotopic` stays default False. See docs/RUNS.md 024.
