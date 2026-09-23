Sprint 025: membrane noise, eta ~ N(0, sigma) added to every neuron's
drive, every substep, every circuit (dynamics.NoiseConfig). Calibrated
via an N=50-per-sigma sweep (Pool(8)) on level 1-1: sigma<=0.03 gives
zero measurable spread across 50 different seeds (the pre-025 system
really is that deterministic); sigma>=0.07 breaks DNp01's commit rate
outright (drops from 50/50 to 9-15/50) and survival jumps 0%->22%+ --
a different, disruptive regime, not "realistic jitter". Picked
sigma=0.04: first clean whole-frame spread (IQR=1.0, range 147-152
around the deterministic 148) while DNp01 still fires in every episode
and survival only ticks up 0%->4%.

projects/legacy/runs/025b_noise_bad.mp4 (seed 5): commit one frame late (149) cascades
into dying at frame 406 instead of 689. projects/legacy/runs/025a_noise_good.mp4 (seed
25): "survives" 800 frames despite an even later commit (152) -- but
it's a stuck-oscillation artifact (max_x_abs=658 vs baseline's 1432),
not better escape, flagged as the separate finding the pre-registration
anticipated. Neither matches "earlier commit clears a Goomba the
baseline hit" -- baseline never fails the first encounter at this
sigma, so there was nothing to correct; reported as found, not reshaped
to fit the hypothesis. See docs/RUNS.md 025 for the full sweep table.
