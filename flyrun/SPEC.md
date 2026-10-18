# flyrun spec excerpts

## B9 Pit (rev 2026-10-18)
A pit of width W (px, measured from the missing floor tiles) is drawn as two invented boxes:
(1) BASE: fills the hole, near edge → far edge, one tile (16 px) deep at floor level. It marks 'pit is still the threat' until his body is past the far edge.
(2) TOWER: 16 px wide, standing on the pit's FAR edge (its near face = the far edge of the hole), Tower base = the HIGHEST surrounding ground of the pit: max(near-rim ground, far-rim ground), where each rim is the top of the solid column at that edge (floor, stair step, block, etc.). Tower top = that base − min(W, MAX_JUMP_HEIGHT). Never anchored to the floor. Expected take-off ≈ 0.25·W before the near edge (+ the measured ~8 px trigger offset). Once released mid-air, the tower stays released (θ 0) until landing — no re-appearance.
The tower is treated exactly like a pipe face: height rule θ = 2·atan(h/2d) with 2-D distance; measured from the take-off ground while airborne; release once feet are above its top AND he is over it.
INVENTED (orange) shape. Replaces the 68 px wall and the S3 true-angle hole.

Note: S3b scaled tower in the middle → wide pits jumped too early (full jump ≈ 84 px fixed). Moved to far edge (S3c).
Note: S3c: pit 3 (between staircases), tower anchored to the floor sat below his feet, nothing loomed, he walked off. (S3d: anchored to the highest rim.)
