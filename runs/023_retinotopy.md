Sprint 023: per-cell receptive fields for LC4/LPLC2 (`retinotopy.py`),
replacing the uniform theta/dtheta broadcast with a Gaussian per-cell
weight over each cell's real, synapse-derived RF centre. Paired
comparison, level 1-1, same conditions as 016/017: baseline reproduced
017 exactly (807 frames, 10 escape commitments, died/flagged). The
retinotopic run died at frame 170 having fired zero escape jumps — the
invented "foveal" edge of the azimuth map sits at the sparsest part of
each population's real RF distribution, so LC4/LPLC2 activation is
LOWEST exactly when a threat is most imminent (d_px≈0), starving
DNp01/TTMn of the drive escape needs. Real, checked mechanism, not a
bug. Reverted `retinotopic` to default False — this is a documented
negative result, not a shipped improvement. See docs/RUNS.md 023.
