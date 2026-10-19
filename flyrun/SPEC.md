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


Scenes test one sense at a time: other senses are switched off with their toggles. Combining senses (and balancing their gains) comes later, by evolution. Q1 note: block 336 missed because pipe 1's looming added to the hum at the Giant Fiber → early jump.

M Smell. The live mushroom (power-up slot) smells sweet. It is drawn as a GREEN box over the mushroom.
- Which antenna: the left-antenna attractive ORNs (DM1, VA2, DM4, left) if it is left of Mario's centre; the right-antenna ones if it is right.
- Strength: SMELL_GAIN × θ_mush (theta_of, 2-D distance from the eye to the mushroom centre, size 16 px).
- Route: real wiring ORN → PN → … → LAL030 → DNa (O0) → steering.
INVENTED (orange): the smell cue and SMELL_GAIN. Toggle: SMELL_SENSE.
Note (Q2): with no smell, the mushroom was eaten only because he was stuck at pipe 1; mushroom-ahead is eaten by walking, so it isn't a smell test.

Four drives, each toggleable: looming (enemy/pipe/pit), home, hum, smell. Every scene states which are on. (Toggles: enemy looming = the `enemy_input` run switch, PIPE_SENSE, PIT_SENSE, HOME_SENSE, HUM_SENSE, SMELL_SENSE; every M2b+ run log records the set via `knobs.toggle_set`.)
M2 note: M2: the turn happened only after pipe 2 stopped him; the no-smell fly also ate it by contact; margin 2e-5 (smell ≈ home). Not yet a real test.

Colour language: red = danger (looming), green = pleasant (hum, smell), white = home. Teal/orange (fly vs invented) stays for labels. Overlay (C1): RED boxes = everything that looms (enemies, pipe faces, pit towers; the pit base as a thin red outline); GREEN line under a humming '?' block (hum level as a number); GREEN box over the mushroom (smell L/R as numbers); WHITE circle at the right edge of the screen at Mario's eye height, size / opacity ~ the HOME_R input (hidden when HOME_SENSE is off); readout strip: active toggle set, TTMn vs threshold, steer vs +-0.01, buttons.

Big Mario (C1a): Mario's box is read from the power-up byte 0x0756 (0 small 12 x 16; 1 big / 2 fire 12 x 24; feet reference 0xCE unchanged). It sets the eye point (hum, smell) and the head-side gap of every threat. The cleared-enemy test and the face / tower "feet above top" tests are feet- and width-based and do not depend on his height.

Regression rule: when the brain changes (more neurons, new row-normalisation), "regression" = the same flags and the same causes of death on the same episodes, NOT frame-identical traces. Extra neurons perturb TTMn by <= ~0.002 (GF-row renormalisation) and, at sigma 0.05, change the noise draw order, so a release can move by one frame. (Accepted at C1: the 881-neuron arm A is the new baseline: 9/10 flags, the same pit-1 death as S3e.) A change of the SENSES code with the brain fixed is still held to frame-identical.

AV Sour smell + back up.
- Every live enemy (Goomba, green/red Koopa, piranha) smells sour. Only the nearest enemy is smelled.
- Sour level = SOUR_GAIN × θ_enemy (same theta_of geometry), fed equally into the left and right DC4 (acid) ORNs.
- Real wiring: DC4 → … → MDN (moonwalker).
- 4th output 'back up': MDN mean > MDN_THRESH (0.10) → press Left and release Right (A unaffected).
- Headroom looming: an enemy's loom input is multiplied by min(1, rise_available / rise_needed), where:
  - rise_available = level.headroom over the span from Mario to the enemy (min of 68 and ceiling − head);
  - rise_needed = the enemy's height + 2 px clearance.
  - Faces and pit towers are unchanged for now.
- INVENTED (orange): the sour cue, SOUR_GAIN, MDN_THRESH, the headroom factor rule. Real (teal): DC4 → MDN.
- Toggles: SOUR_SENSE, HEADROOM_LOOM.
Implementation notes (AV1): (1) "Nearest" = the smallest 2-D gap (the loom's), among enemies not behind his left edge and not cleared in this jump; a shell does not smell sour. (2) The headroom is measured from the take-off ground (like the faces and towers), because in the air his head is already up and the factor would flicker to 0 under any block. (3) The sour brain = the 881 brain + the 26 DC4 -> MDN k/N neurons, built READ-ONLY: edges from the new neurons onto the old ones are dropped, so every old row is exactly as before (flyrun/av1_brain.py; with them the old smell steering broke). (4) SOUR_GAIN = 8.0587: the steady drive at which MDN = 0.10 is 7.0326, divided by theta(50 deg) = 0.8727 rad (runs/AV1_sour_gain.json); frozen.
