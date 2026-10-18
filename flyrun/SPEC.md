# flyrun spec excerpts

## B9 Pit (rev 2026-10-18)
A pit of width W (px, measured from the missing floor tiles) is drawn as two invented boxes:
(1) BASE: fills the hole, near edge → far edge, one tile (16 px) deep at floor level. It marks 'pit is still the threat' until his body is past the far edge.
(2) TOWER: 16 px wide, centred over the hole's midpoint, height = min(W, MAX_JUMP_HEIGHT) above the floor.
The tower is treated exactly like a pipe face: height rule θ = 2·atan(h/2d) with 2-D distance; measured from the take-off ground while airborne; release once feet are above its top AND he is over it.
Expected take-off ≈ 0.75·W before the near edge (W=32 → ~24 px, W=48 → ~36 px).
INVENTED (orange) shape. Replaces the 68 px wall and the S3 true-angle hole.
