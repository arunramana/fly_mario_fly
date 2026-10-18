# flyrun spec excerpts

## B9 Pit (rev 2026-10-18)
A pit of width W (px, measured from the missing floor tiles) is drawn as two invented boxes:
(1) BASE: fills the hole, near edge → far edge, one tile (16 px) deep at floor level. It marks 'pit is still the threat' until his body is past the far edge.
(2) TOWER: 16 px wide, standing on the pit's FAR edge (its near face = the far edge of the hole), Tower base = the HIGHEST surrounding ground of the pit: max(near-rim ground, far-rim ground), where each rim is the top of the solid column at that edge (floor, stair step, block, etc.). Tower top = that base − min(W, MAX_JUMP_HEIGHT). Never anchored to the floor. Expected take-off ≈ 0.25·W before the near edge (+ the measured ~8 px trigger offset). Once released mid-air, the tower stays released (θ 0) until landing — no re-appearance.
The tower is treated exactly like a pipe face: height rule θ = 2·atan(h/2d) with 2-D distance; measured from the take-off ground while airborne; release once feet are above its top AND he is over it.
INVENTED (orange) shape. Replaces the 68 px wall and the S3 true-angle hole.

Note: S3b scaled tower in the middle → wide pits jumped too early (full jump ≈ 84 px fixed). Moved to far edge (S3c).
Note: S3c: pit 3 (between staircases), tower anchored to the floor sat below his feet, nothing loomed, he walked off. (S3d: anchored to the highest rim.)

## Threat choice (S3e)
Enemy cleared = his feet are at or above the enemy's top AND his body is over it (same test as pipe faces / towers). A cleared enemy drops out of the candidates for the rest of this jump (until landing), so the next threat ahead (e.g. the second Goomba of a pair) is chosen and drawn. Landing on a cleared enemy is still allowed (stomp = safe).
Note: S3d: with a Goomba pair, Goomba 1 stayed chosen until he was past it; Goomba 2 was invisible mid-jump (Arun, 2026-10-18).

## Q: ?-blocks and mushroom
Q1 Hum. Every UNUSED, REACHABLE '?' block (tiles 192/193; reachable = bottom ≤ 64 px above the ground under it) hums. Only the nearest humming block ahead of or above him is heard (like the next-threat eye). Loudness = HUM_GAIN × θ_block, where θ_block = the block's angular size from his eye (same theta_of as looming: 2-D distance from the eye point to the block's bottom-centre, size = 16 px). The hum drives the 20 direct JO→GF neurons (13 JO-B1_a, 6 JO-B1_c, 1 JO-CA1) equally; their wiring is real. Once the block is used (tile 35/196) its hum is 0. Jump = the existing fly-held jump (press when TTMn ≥ thresh, hold while above, landing reset). Drawn as a GREEN line under the block. INVENTED (orange): the hum cue and HUM_GAIN. Real (teal): JO → GF → TTMn. Toggle: HUM_SENSE on/off.
Implementation notes (Q1): the eye point is the top-front corner of MARIO_BOX, (mx + 12, feet − 16), as in S3; "ahead of or above" = the block is not fully behind his left edge (bx + 16 > mx); the nearest is by that distance. Brain = W_steer + the 20 JO neurons only (`tutorials/_cache/W_steer_jo.npy`, `steer_jo_bodies.parquet`; `flyrun/q1_brain.py`).

