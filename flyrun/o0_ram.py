"""Part O0 section 4 (RAM / tiles facts, scripted inputs only, no fly): ?-blocks, the mushroom, the power-up state, enemy removal, the mushroom-behind setup.
python -m flyrun.o0_ram        -> prints the facts, writes flyrun/runs/O0_ram.json, O0_mushroom_trace.csv and the two clips.
Every helper here pokes RAM for the SCENE only (removing enemies); nothing in the fly's senses / brain / motor changes."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import env as E
from . import level
from .run import _get_env

ROOT = Path(__file__).resolve().parent
ADDR_ACTIVE, ADDR_TYPE, ADDR_STATE, ADDR_PAGE, ADDR_X, ADDR_Y, ADDR_XSPD, ADDR_YSPD = 0x0F, 0x16, 0x1E, 0x6E, 0x87, 0xCF, 0x58, 0xA0
MUSHROOM_SLOT, MUSHROOM_TYPE = 5, 0x2E          # found below: the power-up has its own (6th) object slot, type byte 0x2E (= E.POWERUP_ID)
ADDR_POWERUP, ADDR_SIZE, ADDR_COINS = 0x0756, 0x0754, 0x075E
ADDR_BBOX = 0x04AC                               # player bounding box: UL_x, UL_y, LR_x, LR_y


def sg(v):
    return v - 256 if v > 127 else v


class Sim:
    """A thin wrapper around the shared emulator with optional enemy removal and per-frame tracing."""

    def __init__(self, remove=True):
        self.env = _get_env()
        self.env.reset()
        self.ram = self.env.unwrapped.ram
        self.remove, self.removed, self.frame = remove, 0, 0
        self.frames = []

    def rm(self):
        """Zero the active flag of the ENEMY slots 0-4 (the power-up lives in slot 5, so it is never touched)."""
        if not self.remove:
            return
        for s in range(5):
            if self.ram[ADDR_ACTIVE + s]:
                self.ram[ADDR_ACTIVE + s] = 0
                self.removed += 1

    def step(self, action, record=False):
        self.rm()
        state, _, done, info = self.env.step(action)
        if record:
            self.frames.append(np.asarray(state).copy())
        self.frame += 1
        return done, info

    @property
    def mx(self):
        return E.mario_x(self.ram)

    def powerup(self):
        r = self.ram
        s = MUSHROOM_SLOT
        if not r[ADDR_ACTIVE + s]:
            return None
        return dict(slot=s, type=int(r[ADDR_TYPE + s]), state=int(r[ADDR_STATE + s]), x=int(r[ADDR_PAGE + s]) * 256 + int(r[ADDR_X + s]),
                    y=int(r[ADDR_Y + s]), xspd=sg(int(r[ADDR_XSPD + s])), yspd=sg(int(r[ADDR_YSPD + s])))

    def bbox(self):
        return [int(self.ram[ADDR_BBOX + i]) for i in range(4)]


def walk_to(sim, x, record=False):
    while sim.mx < x:
        sim.step(E.RIGHT, record)


def hit_from_below(sim, block_x, record=False, hold=14, after=1, tail=E.NOOP):
    """Walk to just before the block, then jump with A held `hold` frames (Right+A): head hits the block from below."""
    walk_to(sim, block_x - 18, record)
    log = []
    for f in range(hold + after):
        sim.step(E.RIGHT_A if f < hold else tail, record)
        log.append((f, sim.mx, int(sim.ram[0xCE]), level.tile(sim.ram, block_x, 7)))
    return log


def main():
    out = {}
    # ---- tiles: the first "?" (x 256, row 7, id 192) and the mushroom "?" (x 336, row 7, id 193)
    sim = Sim()
    coins0 = int(sim.ram[ADDR_COINS])
    score0 = int(sim.env.unwrapped.ram[0x07DE:0x07E4].tolist()[0]) if False else 0
    ids_seen, bump_frames = [level.tile(sim.ram, 256, 7)], 0
    log = hit_from_below(sim, 256)
    for f in range(40):
        sim.step(E.NOOP)
        log.append((f, sim.mx, int(sim.ram[0xCE]), level.tile(sim.ram, 256, 7)))
    seq = []
    for _, _, _, t in log:
        if not seq or seq[-1][0] != t:
            seq.append([t, 0])
        seq[-1][1] += 1
    out["hit_256"] = dict(tile_sequence=seq, coins_before=coins0, coins_after=int(sim.ram[ADDR_COINS]), power_slot_active=bool(sim.powerup()), power_state=int(sim.ram[ADDR_POWERUP]))
    print("hit ? at x 256: tile id sequence (id, frames)", seq, "| coins", coins0, "->", int(sim.ram[ADDR_COINS]), "| power-up slot active:", bool(sim.powerup()))
    # ---- the mushroom block
    sim = Sim()
    log = hit_from_below(sim, 336)
    seq = []
    for _, _, _, t in log:
        if not seq or seq[-1][0] != t:
            seq.append([t, 0])
        seq[-1][1] += 1
    trace, eaten_at, hit_frame = [], None, sim.frame - len(log) + 8
    for f in range(400):
        sim.step(E.NOOP)
        p = sim.powerup()
        trace.append(dict(frame=sim.frame, mario_x=sim.mx, mario_feet=int(sim.ram[0xCE]), powerup_state=int(sim.ram[ADDR_POWERUP]), size_flag=int(sim.ram[ADDR_SIZE]),
                          bbox=" ".join(map(str, sim.bbox())), tile336=level.tile(sim.ram, 336, 7), **({f"m_{k}": v for k, v in p.items()} if p else {}), mushroom_active=int(bool(p))))
        if p is None and f > 20 and eaten_at is None:
            eaten_at = sim.frame
            break
    tr = pd.DataFrame(trace)
    tr.to_csv(ROOT / "runs" / "O0_mushroom_trace.csv", index=False, lineterminator="\n")
    print("hit ? at x 336: tile id sequence", seq)
    first = tr[tr.mushroom_active == 1].iloc[0]
    print("mushroom first seen at frame", int(first.frame), "slot", int(first.m_slot), "type", hex(int(first.m_type)), "x", int(first.m_x), "y", int(first.m_y))
    emerge = tr[(tr.mushroom_active == 1) & (tr.m_xspd == 0)]
    slide = tr[(tr.mushroom_active == 1) & (tr.m_xspd != 0)]
    print("emerging (xspd 0): frames", int(emerge.frame.min()), "-", int(emerge.frame.max()), "(", len(emerge), "frames ), state", int(emerge.m_state.min()), "->", int(emerge.m_state.max()), ", y", int(emerge.m_y.max()), "->", int(emerge.m_y.min()))
    print("sliding starts at frame", int(slide.frame.min()), "x", int(slide.m_x.iloc[0]), "xspd", int(slide.m_xspd.iloc[0]))
    s = slide.reset_index(drop=True)
    vx = s.m_x.diff()
    flips = s[(s.m_xspd.diff() != 0) & (s.index > 0)][["frame", "m_x", "m_y", "m_xspd"]]
    print("speed changes (flip / bounce):\n", flips.to_string(index=False))
    mov = s[s.m_xspd == 16]
    print("px/frame while xspd 16: median", float(vx[s.m_xspd == 16].median()), "| falling off the brick row: y", int(s.m_y.min()), "->", int(s.m_y.max()))
    print("eaten at frame", eaten_at, "| power-up state", int(sim.ram[ADDR_POWERUP]), "size flag", int(sim.ram[ADDR_SIZE]), "| mushroom slot active:", bool(sim.powerup()))
    out["mushroom"] = dict(block_tile_sequence=seq, first_frame=int(first.frame), slot=int(first.m_slot), type=int(first.m_type),
                           emerge_frames=len(emerge), emerge_state=[int(emerge.m_state.min()), int(emerge.m_state.max())],
                           emerge_y=[int(emerge.m_y.max()), int(emerge.m_y.min())], slide_start_frame=int(slide.frame.min()), slide_xspd=int(slide.m_xspd.iloc[0]),
                           px_per_frame=float(vx[s.m_xspd == 16].median()), flips=flips.to_dict("records"), eaten_frame=eaten_at,
                           powerup_after=int(sim.ram[ADDR_POWERUP]), size_flag_after=int(sim.ram[ADDR_SIZE]))
    # ---- Mario small vs big
    small = tr.iloc[0]
    for _ in range(40):
        sim.step(E.NOOP)
    big_bbox = sim.bbox()
    print("bounding box small:", small.bbox, "| big (after growing):", big_bbox, "| power-up", int(sim.ram[ADDR_POWERUP]), "size flag", int(sim.ram[ADDR_SIZE]))
    out["bbox"] = dict(small=small.bbox, big=big_bbox, powerup_state_big=int(sim.ram[ADDR_POWERUP]))
    out.update(mushroom_clip())
    out.update(part_blocks())
    out.update(part_remove())
    out.update(part_m2())
    json.dump(out, open(ROOT / "runs" / "O0_ram.json", "w"), indent=1, default=float)


def mushroom_clip():
    """clips/O0_mushroom.mp4: the scripted '?' hit at x 336, the mushroom coming out, sliding, bouncing off pipe 1 and being eaten (0.5x)."""
    sim = Sim()
    walk_to(sim, 336 - 18)
    n0 = len(sim.frames)
    rows, k_eat = [], None
    for f in range(400):
        a = E.RIGHT_A if f < 14 else E.NOOP
        sim.step(a, record=True)
        p = sim.powerup()
        rows.append([f"O0: scripted '?' hit at x 336 (enemies removed)", f"Mario x {sim.mx}  feet {int(sim.ram[0xCE])}  block tile {level.tile(sim.ram, 336, 7)}  power-up state {int(sim.ram[ADDR_POWERUP])}",
                     (f"mushroom slot {p['slot']} type {hex(p['type'])} x {p['x']} y {p['y']} state {p['state']} xspd {p['xspd']}" if p else "mushroom slot 5: inactive")])
        if f > 30 and p is None and k_eat is None:
            k_eat = f
        if k_eat is not None and f > k_eat + 40:
            break
    frames = sim.frames
    clip(frames, rows, ROOT / "clips" / "O0_mushroom.mp4", fps=30)
    return {"mushroom_clip": dict(frames=len(frames), eaten_index=k_eat)}


def clip(frames, texts, path, fps=30, S=3):
    import cv2
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w * S, h * S))
    for img, lines in zip(frames, texts):
        im = cv2.cvtColor(cv2.resize(np.ascontiguousarray(img), None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST), cv2.COLOR_RGB2BGR)
        for i, t in enumerate(lines):
            cv2.putText(im, t, (8, 20 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(im, t, (8, 20 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        vw.write(im)
    vw.release()
    print("clip", path.name, len(frames), "frames = %.1f s" % (len(frames) / fps))


def part_blocks():
    """Every ? in 1-1 (from the scripted tile scan), reachability from the ground, and the contents (hit tests for 256 / 336 / 368 / 1248 / 1744)."""
    tiles = json.load(open(ROOT / "runs" / "O0_tiles_1-1.json"))
    rows = []
    MAXJ = 68
    for wx, r, t in tiles:
        if t not in (192, 193):
            continue
        bottom = (r + 1) * 16                                  # y of the block's underside (tile-buffer y; ground top = 176)
        height = 176 - bottom                                   # block underside above the ground under it
        rise = (176 - 16) - bottom + 16 if False else 176 - (bottom + 16)   # small Mario's feet must rise this far for his head (feet - 16) to reach the underside
        rows.append(dict(x=wx, row=r, tile=t, underside_above_ground=height, small_mario_rise_needed=rise, reachable_from_ground=rise <= MAXJ,
                         contents="mushroom (power-up)" if t == 193 else "coin"))
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    df.to_csv(ROOT / "runs" / "O0_qblocks.csv", index=False, lineterminator="\n")
    # contents check by hitting: first-hit tests on the ground-reachable blocks that are on the way (x 256 coin, 336 mushroom shown above); 368 here
    res = {}
    sim = Sim()
    c0 = int(sim.ram[ADDR_COINS])
    hit_from_below(sim, 368)
    for _ in range(30):
        sim.step(E.NOOP)
    res["hit_368"] = dict(tile=level.tile(sim.ram, 368, 7), coins=int(sim.ram[ADDR_COINS]) - c0, power_slot=bool(sim.powerup()))
    print("hit ? at x 368:", res["hit_368"])
    # big Mario (RAM poke for the measurement only: power-up state 1, size flag 0): a head bump happens higher up the jump than for small Mario
    def bump_feet(big):
        sm = Sim()
        if big:
            sm.ram[ADDR_POWERUP], sm.ram[ADDR_SIZE] = 1, 0
            for _ in range(5):
                sm.step(E.NOOP)
        walk_to(sm, 256 - 18)
        for f in range(30):
            sm.step(E.RIGHT_A)
            if level.tile(sm.ram, 256, 7) != 192:
                return int(sm.ram[0xCE]), int(sm.ram[ADDR_SIZE]), sm.bbox()
        return None, int(sm.ram[ADDR_SIZE]), sm.bbox()
    sb, bb = bump_feet(False), bump_feet(True)
    print("head bump under a block whose underside is y 128: small feet y", sb[0], "bbox", sb[2], "| big feet y", bb[0], "bbox", bb[2], "(size flag", bb[1], ")")
    res["height"] = dict(small_bump_feet=sb[0], big_bump_feet=bb[0], small_bbox=sb[2], big_bbox=bb[2])
    # the 1248 mushroom block with the scripted driver (best effort)
    from . import scripted
    sim = Sim()
    drv = scripted.Driver()
    for f in range(4000):
        if sim.mx >= 1226 and int(sim.ram[0x001D]) == 0:
            break
        done, _ = sim.step(drv.act(sim.ram))
        if done:
            break
    if sim.mx >= 1226 and level.tile(sim.ram, 1248, 7) == 193:
        for f in range(16):
            sim.step(E.RIGHT_A if f < 14 else E.NOOP)
        res["hit_1248"] = dict(tile=level.tile(sim.ram, 1248, 7), mushroom_slot=bool(sim.powerup()), mario_x=sim.mx)
        for _ in range(80):
            sim.step(E.NOOP)
        res["hit_1248"]["mushroom_after_80"] = sim.powerup()
    else:
        res["hit_1248"] = dict(reached=sim.mx)
    print("hit ? at x 1248:", res["hit_1248"])
    res["qblocks"] = rows
    return res


def part_remove():
    """Enemy removal: zero the active flags of enemy slots 0-4 every frame, scripted driver on the first ~600 px."""
    from . import scripted
    out = {}
    for remove in (False, True):
        sim = Sim(remove=remove)
        drv = scripted.Driver()
        first_enemy_frame, mx_at_death = None, None
        for f in range(1200):
            if sim.mx >= 640:
                break
            if first_enemy_frame is None and any(sim.ram[ADDR_ACTIVE + s] for s in range(5)):
                first_enemy_frame = f
            done, info = sim.step(drv.act(sim.ram))
            if done:
                mx_at_death = sim.mx
                break
        out["removal_on" if remove else "removal_off"] = dict(frames=f, reached_x=sim.mx, died_at=mx_at_death, enemies_zeroed=sim.removed, first_enemy_frame=first_enemy_frame)
    print("enemy removal (scripted driver, x<640): off ->", out["removal_off"], "| on ->", out["removal_on"])
    return {"removal": out}


def part_m2():
    """Mushroom behind Mario. Scripted ? hit at x 336 (the mushroom comes out), scripted run to flat ground past pipe 1 (x >= 560), then the
    mushroom is re-placed by a RAM poke 64 px behind Mario, moving RIGHT (toward him), and the fly takes over."""
    from . import scripted
    out = {}
    D = 64
    for variant in ("natural", "placed"):
        sim = Sim()
        hit_from_below(sim, 336, record=True)
        drv = scripted.Driver()
        for f in range(1200):
            if sim.mx >= (500 if variant == "natural" else 560) and int(sim.ram[0x001D]) == 0 and sim.powerup():
                break
            sim.step(drv.act(sim.ram), record=True)
        p0 = sim.powerup()
        if variant == "placed":
            x = sim.mx - D
            r, sl = sim.ram, MUSHROOM_SLOT
            r[ADDR_PAGE + sl], r[ADDR_X + sl] = x // 256, x % 256
            r[ADDR_Y + sl] = 184                              # on the ground (enemy y = feet + 8)
            r[0x46 + sl] = 1                                  # Enemy_MovingDir: 1 = right
            r[ADDR_XSPD + sl] = 16
        p = sim.powerup()
        info = dict(frame=sim.frame, mario_x=sim.mx, mario_feet=int(sim.ram[0xCE]), mushroom_before_poke=p0, mushroom_at_handover=p, mushroom_minus_mario=(p["x"] - sim.mx) if p else None)
        print(f"M2 ({variant}) hand-over:", info)
        n_hand = len(sim.frames)
        track = []
        walk = variant == "placed" and False
        for f in range(240):
            sim.step(E.NOOP, record=True)
            q = sim.powerup()
            track.append(dict(frame=sim.frame, mario_x=sim.mx, mushroom_x=q["x"] if q else None, mushroom_xspd=q["xspd"] if q else None, mushroom_y=q["y"] if q else None,
                              powerup_state=int(sim.ram[ADDR_POWERUP])))
        tr = pd.DataFrame(track)
        print(f"   Mario standing still, mushroom x every 30 frames:", [(int(a), None if pd.isna(b) else int(b), None if pd.isna(c) else int(c)) for a, b, c in tr[["frame", "mushroom_x", "mushroom_xspd"]].iloc[::30].to_numpy()],
              "| power-up state at the end", int(tr.powerup_state.iloc[-1]))
        out[variant] = dict(handover=info, track=tr.iloc[::30].to_dict("records"))
        if variant == "placed":
            frames = sim.frames
            k0 = max(0, n_hand - 50)
            sel = list(range(k0, min(len(frames), n_hand + 130)))
            texts = [[f"O0 M2 setup (scripted + one RAM poke): mushroom {D} px behind Mario, moving right", "HAND-OVER" if i == n_hand else ("scripted run" if i < n_hand else "Mario standing still after hand-over")] for i in sel]
            clip([frames[i] for i in sel], texts, ROOT / "clips" / "O0_m2_setup.mp4", fps=30)
    return {"m2": out}


if __name__ == "__main__":
    main()
