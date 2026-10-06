# Investigation: the x 722-724 stall in the 1-1 baseline (B11, obstacle expansion on)

2026-10-05. Read-only. All "episode" numbers are REPLAYS of the five stuck real-arm episodes of audit/p7_b11.json (seeds 6103, 6105, 6106, 6108, 6115; the replay reproduced outcome, max_x and frame count exactly; no new eval, no seed outside 6100-6119). Scripted-geometry runs used only scripted buttons (no fly), the Phase 6 harness (enemy slots zeroed). Scripts: audit/p9s_replay.py, p9s_an.py, p9s_dbg.py, p9s_scan.py, p9s_hop3.py (gitignored). [M] measured, [I] inferred.

## Answer
1. x 724 is **pipe 3**: tile columns x 736-767, rows 7-10 = **4 tiles = 64 px high** (tiles 0x12/0x13 tops, 0x14/0x15 body). Mario (small) stalls at x 722-724, 12-14 px short of the face. Solid, drawn, correctly classified; no gap or block involved. [M]
2. **Not a geometry or classification error, and not the cue failing to fire.** The cue fires early (GF first spike x 659-663, d 73-77 px, theta ~43 deg) while Mario is still airborne from the pipe-2 hop. The A presses (14-17 frames, first press d 71-77, long press d 52-57) all start in the air and none is a ground take-off. [M]
3. At the wall the cue is **silent by construction**: the elevation weight. Face centre is 24 px above small Mario's centre (pipe 3 = 64 px), and at d 14 that is 59.7 deg elevation against the 60 deg limit, so theta = 0.6 deg (measured, last 100 frames of all 5 episodes: theta 0.6, GF 0 spikes, A 0 frames). Nothing presses A for the 300 stuck frames. [M]
4. Even on the ground the cue would barely fire. Computed theta(d) for a grounded small Mario (brain/obstacles.theta_of): pipe 1 peak 50.2 deg, pipe 2 peak 41.1 (d 32), pipe 3 peak 37.7 (d 44). The GF's first spike in these replays came at 39-48 deg (no non-spike frame at x>=640 ever exceeded 43.7 deg). So grounded, pipe 3 stays below where the GF fires [I; threshold read off 94 spike frames, not a fitted value]. The five fired only because Mario was airborne (lower centre, smaller elevation). [M for the replays, I for the grounded case]

## Per episode (frames from reset, x = Mario world x, d = face 736 minus x)
| seed | in air at x 640 | GF first spike (frame, x, d, theta) | A presses (start frame / x / len) | landed (x, d) | A fresh press on ground after x 640 | end |
|---|---|---|---|---|---|---|
| 6103 | yes | f476, 662, 74, 43.2 | f477/665/1; f482/680/16 | f496, 722, 14 | 0 | stuck f796 |
| 6105 | yes | f469, 662, 74 | f469/662/1; f476/683/14 | f488, 719, 17 | 0 | stuck f789 |
| 6106 | yes | f471, 663, 73 | f471/1; f473/1; f478/684/16 | f490, 720, 16 | 0 | stuck f790 |
| 6108 | yes | f472, 661, 75 | f473/664/1; f478/679/16 | f492, 721, 15 | 0 | stuck f792 |
| 6115 | yes | f241, 659, 77 | f241/659/17 (ends x 707) | f259, 713, 23 | 0 | stuck f562 |
Cue trace (6103, theta deg by d): 95 px 28, 62 px 42, 47 px 58, 38 px 70, 32 px 72, 23 px 49, 14 px 0. The 70-80 deg peaks are airborne. Spike trains run every frame from d ~75 to d ~20 then stop (theta falls as the elevation weight drops). [M]
- Every run starts at an upward re-bounce at x 674-677 (vy -4 while A=0 on the previous frame): in 6103 a stationary Goomba (slot 1, x 671) is on the path, so a stomp bounce [I]. The hold rose only 5-15 px (measured y change), because it is an air press.
- 4 of 5 landed with A still held from the air (A on frames 496-497 etc., released x 722-724). SMB starts a jump only on a fresh A edge, so a held A across the landing gives no take-off [I, from game-engine knowledge, not tested here]. After landing no A press follows (cue silent). 6115 landed at d 23, released A 6 frames earlier at x 707.

## Hold needed vs available (scripted, grounded, running 3 px/frame, press at distance before the stall point; [M] audit/p9s_hop3.py)
- Needed apex > 64 px (floor top y 208, pipe top y 144). Apex by hold (unobstructed): 8 -> 56, 10 -> 64, 12 -> 67, 16 -> 75, 24 -> 85 (matches Phase 6).
- Pipe 3 cleared (x >= 772, standing): hold <= 8 never; hold 10 at 8-17 and 35 px, not 26 (marginal); hold 12/14/16 at 8-35 px before stall; hold 24 at 0-35. Take-off window for hold 12: face distance ~22-49 px (grid ~9 px, 0 px fails).
- The observed A runs (14-17 frames) are long enough; the failure is timing/airborne state and the silent cue, not hold length. A ground press 8-35 px before the stall point (d 22-49) with a hold >= 12 would clear. Closed-loop first-run holds were median 4 / max 8 in Phase 3b, below 10 [Phase 6 doc].

## What lies between x 722 and the flag (read-only scripted walk, tile buffer, `audit/p9s_cols.json`)
Scan reached x ~2730 (the scripted walker died in the 32 px gap at x 2448, so the last ~430 px before the flag, including the end staircase and flagpole, are NOT scanned) [M for scanned part].
- Pipes: pipe 3 (x 736, 64 px, the stall), pipe 4 (x 912, 64 px). Both 64 px: need hold >= 12.
- Gaps: x 1104 (32 px), x 1376-1423 (~48 px, floor tiles absent under a brick row), x 2448 (32 px); gaps need the (unmodelled) gap cue, not the obstacle cue.
- Stairs (16 px steps, x 2144-2288 up/down, 2368-2432 up, 2480-2528 down; 64 px at the top). Steps are 16 px apiece so a 16-px hop each, but the first step column in the cue is a 16 px face (weak theta).
- Bricks/"?" blocks (0x51/0xC0/0xC1/0x60) at head height rows 3-7 (x 256-384, 1232-1344, 1504, 1744, ...). The cue reads any non-zero tile as solid; blocks overlapping Mario's body span would register as faces. Not examined for false positives in this note.
- Flag and end stairs (x ~3100-3200) are from memory, not measured.

## Verdict on the candidate causes
| cause | verdict |
|---|---|
| cue not firing (view range, run-length rule) | no: fires at d 73-77 (airborne) |
| GF too early | yes in effect: the train starts at d ~75 while Mario is still airborne; A presses land on the air, not the ground [M] |
| GF too late | no |
| 1-frame tap | no: the long presses are 14-17 frames; 1-frame taps at d 67-77 also in the air |
| geometry/solid classification | no: pipe tiles 0x12-0x15, 64 px, correct |
| silent cue at the wall (elevation weight, 24 px above centre, theta 0.6 deg at d 14) | **yes, the stall's persistence** [M] |
| grounded theta peak 37.7 deg below the GF's firing level | likely, i.e. the grounded pipe-3 approach would not fire either [I] |

## Open
- Replays used the full closed loop; I did not test whether a pipe-2 landing delayed by a Goomba stomp is a generic effect or specific to seeds 6103-6115 (the Goomba is the same level feature, so likely).
- Whether the SMB fresh-A-edge rule is what suppressed the take-off at landing was not tested (inferred).
- Tall obstacle cue = elevation weight is a property of brain/obstacles.theta_of + ELEVATION_LIMIT_DEG; not changed.
