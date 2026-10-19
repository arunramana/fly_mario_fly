"""Senses v2 (Part S1): ONE threat feeds the loom detectors, the nearest one AHEAD by surface-to-surface gap, re-chosen every frame.

Candidates: live enemies (Goomba / Koopa / shell), the nearest wall/pipe/step face that rises above Mario's FEET, and each empty
pit (S3c: a base over the hole + a tower on its far edge anchored to its highest rim, flyrun/SPEC.md B9). True 2-D distance d = sqrt(gap_x^2 + gap_y^2) between Mario's box and the object's box;
theta = 2 atan(h / 2d) with the object's height h. dtheta is tracked per object identity: when the chosen object changes,
dtheta is 0 at that frame. Threats behind Mario are ignored; floating blocks do not loom (only level.SOLID_WALL columns do).
Nothing here is read from pixels. The v1 class (senses.Senses) is untouched and stays the default."""
from dataclasses import dataclass

import numpy as np

from . import env as E
from . import level
from .knobs import ENEMY_FEET_OFFSET, enemy_types, MARIO_BOX, MARIO_BOX_BIG, HUM_REACH, MAX_JUMP_HEIGHT, PIT_GAIN_V2, SIZE_TABLE
from .senses import Loom, theta_of

ADDR_POWERUP = 0x0756      # 0 small, 1 big, 2 fire (O0)
ADDR_MARIO_Y = 0x00CE      # verified: = Mario's FEET y in tile-buffer coordinates (ground 176 = top of row 11, ledge 112 = top of row 7)
ADDR_ENEMY_Y, ADDR_ENEMY_STATE = 0x00CF, 0x001E
LIVE_STATES = {"goomba": (0, 1), "koopa": (0,), "shell": (2, 3), "piranha": (0,)}   # RAM state bytes; 4 / 0x22 = stomped / defeated -> ignored


@dataclass
class Threat:
    kind: str          # goomba / koopa / shell / face / pit (the hole)
    ident: tuple       # ("enemy", slot) / ("face", column x) / ("pit", column x)
    x: int             # left edge, world px
    top: int           # top edge y (tile-buffer coordinates)
    w: int
    h: int             # the height that sets theta
    d: float = 0.0     # surface-to-surface 2-D gap (px)
    theta: float = 0.0
    rims: tuple = None   # pits only: (near rim y, far rim y, near rim column x, far rim column x)
    base: tuple = None   # pits only: the base box (x, top, w, h); the Threat's own box is then the tower
    dsel: float = 0.0    # distance used to pick between threats
    rear: bool = False   # RE2: an enemy BEHIND him (fully behind his left edge)


def mario_box(ram):
    """C1: Mario's (w, h) from the power-up state (0x0756): small 12 x 16, big / fire 12 x 24 (feet y 0xCE is the same reference for both; his top is 8 px higher)."""
    return MARIO_BOX_BIG if int(ram[ADDR_POWERUP]) >= 1 else MARIO_BOX


def gap(mx, feet, x, top, w, h, box=MARIO_BOX, rear=False):
    """2-D gap between Mario's box and an object's box (0 on an axis where they overlap). rear=True (RE2): the object is behind him, the x gap is measured from his left edge."""
    mw, mh = box
    gx = max(0.0, mx - (x + w)) if rear else max(0.0, x - (mx + mw))
    gy = max(0.0, top - feet, (feet - mh) - (top + h))   # object entirely below Mario's feet / entirely above his head
    return float(np.hypot(gx, gy))


def over(mx, x0, x1, box=MARIO_BOX):
    """His body (box wide, left edge mx) horizontally overlaps the columns [x0, x1)."""
    return mx < x1 and mx + box[0] > x0


def merge_columns(walls):
    """[(x, H)] per column -> [(x0, x1, H)]: neighbouring columns of equal height are ONE face (a pipe is 2 columns wide)."""
    out = []
    for wx, H in walls:
        if out and out[-1][1] == wx and out[-1][2] == H:
            out[-1] = (out[-1][0], wx + level.TILE, H)
        else:
            out.append((wx, wx + level.TILE, H))
    return out


def is_cleared(mx, feet, t, box=MARIO_BOX):
    """S3e: an enemy is cleared when his feet are at or above its top AND his body is over it (the pipe-face / tower test)."""
    return feet <= t.top and over(mx, t.x, t.x + t.w, box)


def hum_block(mx, feet, blocks, box=MARIO_BOX, reach=HUM_REACH, eye_dy=0.0):
    """Q1: the nearest humming block -> (bx, bottom y, d) or None. blocks = [(x, row)] of UNUSED ? blocks. Reachable = the underside is <= 64 px above the ground
    under it (floor 176). Only blocks not fully behind his left edge count. d = distance from his eye (top-front corner of MARIO_BOX) to the block's bottom-centre."""
    ex, ey = mx + box[0], feet - box[1] + eye_dy       # E2: eye_dy lowers the eye point from the top-front corner (0 = the corner, the old behaviour)
    best = None
    for bx, row in blocks:
        bottom = (row + 1) * level.TILE
        if level.ROW_GROUND * level.TILE - bottom > reach or bx + level.TILE <= mx:
            continue
        d = float(np.hypot(ex - (bx + level.TILE / 2), ey - bottom))
        if best is None or d < best[2]:
            best = (bx, bottom, d)
    return best


def mushroom(ram):
    """M2: the live power-up (object slot 5, type byte 0x2E) -> (left x, top y in tile-buffer coordinates) of its 16 x 16 box, or None."""
    sl = E.N_ENEMY_SLOTS
    if not int(ram[E.ADDR_ENEMY_ACTIVE + sl]) or int(ram[E.ADDR_ENEMY_TYPE + sl]) != E.POWERUP_ID:
        return None
    x = int(ram[E.ADDR_ENEMY_PAGE + sl]) * 256 + int(ram[E.ADDR_ENEMY_X + sl])
    return x, int(ram[ADDR_ENEMY_Y + sl]) - ENEMY_FEET_OFFSET - 16


def enemy_boxes(enemies, walls=None):
    """enemies: [(slot, type_byte, state, ex, ey)] -> list of Threat (live, known types only). walls: [(x, H)] from level.scan_visible, used only to clip a piranha plant at its pipe's rim."""
    out = []
    types = enemy_types()
    for slot, typ, state, ex, ey in enemies:
        kind = types.get(typ)
        if kind == "koopa" and state in LIVE_STATES["shell"]:
            kind = "shell"
        if kind is None or state not in LIVE_STATES[kind]:
            continue
        w, h = SIZE_TABLE[kind]
        feet = ey - ENEMY_FEET_OFFSET
        if kind == "piranha":
            # L2b: the plant lives inside its pipe and is drawn behind it: only the part above the rim exists (measured: fully out = its feet at the rim, runs/L2b_enemies.json).
            # The game activates the plant ~90 px before its pipe scrolls in, so a plant whose pipe is not in the visible tile buffer yet is not seen at all.
            cols = dict(walls or [])
            pipe = [cols.get((ex // level.TILE) * level.TILE), cols.get(((ex + w - 1) // level.TILE) * level.TILE)]
            if None in pipe:
                continue
            rim = level.ROW_GROUND * level.TILE - max(pipe)
            h = max(0, min(feet, rim) - (feet - h))
            if h == 0:
                continue
            out.append(Threat(kind, ("enemy", slot), ex, feet - SIZE_TABLE[kind][1], w, h))
            continue
        out.append(Threat(kind, ("enemy", slot), ex, feet - h, w, h))
    return out


SOUR_KINDS = ("goomba", "koopa", "piranha")      # AV1: what smells sour (live Goomba, green / red Koopa, piranha); a shell does not
HEADROOM_CLEARANCE = 2                            # INVENTED (fixed), AV1: px of clearance above the enemy's top that a jump must reach (rise_needed = enemy height + this)


def is_behind(mx, t):
    """RE2: the object is fully behind his left edge."""
    return t.x + t.w <= mx


def sour_enemy(mx, feet, enemies, walls, cleared=frozenset(), box=MARIO_BOX, rear=False):
    """AV1: the nearest live sour enemy (by the same 2-D gap as the loom), with .d and .theta, or None. Like the loom candidates: not behind his left edge, not cleared in this jump.
    RE2: rear=True also takes enemies behind his left edge (the nearest on EITHER side); .rear marks which side the source is on."""
    best = None
    for t in enemy_boxes(enemies, walls):
        if t.kind not in SOUR_KINDS or t.ident in cleared or is_cleared(mx, feet, t, box):
            continue
        if not (t.x >= mx or over(mx, t.x, t.x + t.w, box)):
            if not (rear and is_behind(mx, t)):
                continue
            t.rear = True
        t.d = gap(mx, feet, t.x, t.top, t.w, t.h, box, rear=t.rear)
        if best is None or t.d < best.d:
            best = t
    if best is not None:
        best.theta = theta_of(best.d, best.h)
    return best


def headroom_factor(ram, mx, feet, t, box=MARIO_BOX):    # RE2: a rear enemy's span runs from its left edge to his right edge
    """AV1: min(1, rise_available / rise_needed) for an enemy -> (factor, rise_available, rise_needed). rise_available = level.headroom over the span from Mario's left edge to the enemy's right edge
    (min of MAX_JUMP_HEIGHT and ceiling - head); rise_needed = the enemy's height + HEADROOM_CLEARANCE."""
    x0, x1 = (t.x, mx + box[0]) if t.rear else (mx, max(t.x + t.w, mx + box[0]))
    _, rise = level.headroom(ram, x0, x1, feet, box_h=box[1])
    need = t.h + HEADROOM_CLEARANCE
    return min(1.0, rise / need), rise, need


def rim_top(walls, x):
    """y of the top of the solid column at world x (tile-aligned): the wall column's top if there is one, else the floor."""
    for wx, H in walls:
        if wx == x:
            return level.ROW_GROUND * level.TILE - H
    return level.ROW_GROUND * level.TILE


def choose(mx, feet, enemies, walls, pits, enemy_input=True, pipe_sense=True, pit_sense=True, ground=None, released=frozenset(), cleared=frozenset(), box=MARIO_BOX, pit_pos=1.0, pit_h=1.0, rear_closing=None):
    """-> the chosen Threat (with .d and .theta) or None. walls: [(x, H)] from level.scan_visible, pits: [(x, w)].
    ground = the y of the ground Mario took off from (his current ground while grounded); default = feet (S1 behaviour on the ground).
    released = idents of pit towers already released in this jump: their tower stays 0 until the landing (S3c, no re-appearance).
    cleared = idents of enemies already cleared in this jump (S3e): dropped from the candidates until the landing, so the next threat is chosen.
    rear_closing (RE2, REAR_EYE on): idents of enemies BEHIND him whose gap is shrinking; they compete with the threats ahead by the same 2-D gap. Faces and pits stay ahead-only."""
    ground = feet if ground is None else ground
    cands = []
    if enemy_input:
        cands += [t for t in enemy_boxes(enemies, walls) if t.ident not in cleared and not is_cleared(mx, feet, t, box)]
    if pipe_sense:
        for x0, x1, H in merge_columns(walls):
            top = level.ROW_GROUND * level.TILE - H            # y of the top of that face
            if x1 <= mx:
                continue                                        # fully behind his left edge
            # S2c (B6): the face keeps its full height from the take-off ground until his feet are above its top AND his body
            # is over its columns; only then it is 0 (a step)
            h = 0 if (feet <= top and over(mx, x0, x1, box)) else ground - top
            if h > 0:
                cands.append(Threat("face", ("face", x0), x0, top, x1 - x0, h))
                break                                           # the nearest rising face ahead; later ones are behind it
    if pit_sense:
        for px, pw in pits:
            if mx >= px + pw:                                   # his body is past the far edge: the pit is over (flyrun/SPEC.md B9)
                continue
            # S3d (B9): BASE = the hole (marks "the pit is still the threat"), TOWER = 16 px wide standing on the FAR edge, treated like a pipe
            # face; once released mid-air it stays 0 until landing. Its base is the HIGHEST rim of the pit (the top of the solid column at the
            # near edge / the far edge: floor, stair step, ...), its top = that - min(W, MAX_JUMP_HEIGHT). Never anchored to the floor.
            floor = level.ROW_GROUND * level.TILE
            near_y, far_y = rim_top(walls, px - level.TILE), rim_top(walls, px + pw)
            tower_h = min(pw, MAX_JUMP_HEIGHT) if pit_h == 1.0 else min(pw, MAX_JUMP_HEIGHT) * pit_h        # E2: the tower height as a multiple of W (1 = the old rule)
            top = min(near_y, far_y) - tower_h
            tx = px + pw if pit_pos == 1.0 else px + int(round(pit_pos * pw))                             # E2: 0 = the near edge ... 1 = the far edge (the old rule)
            h = 0 if (("pit", px) in released or (feet <= top and over(mx, tx, tx + level.TILE, box))) else ground - top
            t = Threat("pit", ("pit", px), tx, top, level.TILE, max(h, 0))
            t.base = (px, floor, pw, level.TILE)
            t.rims = (near_y, far_y, px - level.TILE, px + pw)     # overlay: the two rim heights and their columns
            cands.append(t)
    ahead = [t for t in cands if t.x >= mx or t.kind == "pit" or over(mx, t.x, t.x + t.w, box)]
    for t in ahead:
        t.d = gap(mx, feet, t.x, t.top, t.w, t.h, box)
        t.dsel = gap(mx, feet, *t.base, box) if t.base else t.d    # a pit competes with other threats by its nearest part (the base)
        t.theta = PIT_GAIN_V2 * theta_of(t.d, t.h) if t.kind == "pit" and t.h > 0 else (0.0 if t.kind == "pit" else theta_of(t.d, t.h))
    if rear_closing:
        for t in cands:
            if t.ident in rear_closing and is_behind(mx, t):
                t.rear = True
                t.d = t.dsel = gap(mx, feet, t.x, t.top, t.w, t.h, box, rear=True)
                t.theta = theta_of(t.d, t.h)
                ahead.append(t)
    return min(ahead, key=lambda t: t.dsel) if ahead else None


class SensesV2:
    def __init__(self, knobs, masks, K, rng=None):
        self.k, self.m, self.K, self.rng = knobs, masks, K, rng
        self.prev_id, self.prev_theta, self.prev_d = None, 0.0, None
        self.ground = None       # y of the ground he last stood on (the take-off ground while airborne)
        self.released = set()    # pit towers released in the current jump (cleared on landing)
        self.cleared = set()     # enemies cleared in the current jump (S3e; emptied on landing)
        self.rear_gap = {}       # RE2: gap to each enemy behind him on the previous frame (to tell closing from receding)

    def read_ram(self, ram):
        mx = E.mario_x(ram)
        feet = int(ram[ADDR_MARIO_Y])
        enemies = [(s, int(ram[E.ADDR_ENEMY_TYPE + s]), int(ram[ADDR_ENEMY_STATE + s]),
                    int(ram[E.ADDR_ENEMY_PAGE + s]) * 256 + int(ram[E.ADDR_ENEMY_X + s]), int(ram[ADDR_ENEMY_Y + s]))
                   for s in range(E.N_ENEMY_SLOTS) if int(ram[E.ADDR_ENEMY_ACTIVE + s])]
        walls, pits = level.scan_visible(ram, rim=True)
        return mx, feet, enemies, walls, pits

    def look(self, ram, enemy_input=True):
        """-> (I, Loom). Loom.extra carries the chosen threat for the log / clip."""
        mx, feet, enemies, walls, pits = self.read_ram(ram)
        box = mario_box(ram)
        if int(ram[0x001D]) == 0 or self.ground is None:
            self.ground = feet
        if int(ram[0x001D]) == 0:
            self.released.clear()
            self.cleared.clear()
        else:
            self.cleared |= {t.ident for t in enemy_boxes(enemies, walls) if is_cleared(mx, feet, t, box)}
        closing = None
        if self.k.REAR_EYE:
            # RE2: a looming detector answers an EXPANDING object: an enemy behind him counts only while its gap is shrinking (a receding one contracts and does not loom)
            now = {t_.ident: gap(mx, feet, t_.x, t_.top, t_.w, t_.h, box, rear=True) for t_ in enemy_boxes(enemies, walls) if is_behind(mx, t_)}
            closing = frozenset(i for i, d_ in now.items() if i in self.rear_gap and d_ < self.rear_gap[i])
            self.rear_gap = now
        t = choose(mx, feet, enemies, walls, pits, enemy_input, self.k.PIPE_SENSE, self.k.PIT_SENSE, ground=self.ground, released=frozenset(self.released), cleared=frozenset(self.cleared), box=box, pit_pos=self.k.PIT_TOWER_POS, pit_h=self.k.PIT_TOWER_H, rear_closing=closing)
        if t is not None and t.kind == "pit" and t.h == 0 and int(ram[0x001D]) != 0:
            self.released.add(t.ident)
        hf, rise, need, th_raw = 1.0, None, None, None
        if self.k.HEADROOM_LOOM and t is not None and t.kind in ("goomba", "koopa", "shell", "piranha"):
            hf, rise, need = headroom_factor(ram, mx, self.ground, t, box)      # from the take-off ground, like the faces and towers: in the air his head is already up and the factor would flicker
            th_raw, t.theta = t.theta, t.theta * hf
        I, lm = self.from_threat(t)
        if self.k.HEADROOM_LOOM:
            lm.extra.update(headroom_factor=hf, headroom_rise=rise, headroom_need=need, theta_unscaled=th_raw if th_raw is not None else lm.theta)
        if self.k.SOUR_SENSE:
            assert "DC4_L" in self.m, "SOUR_SENSE needs the sour brain (W_steer_jo_orn_sour.npy)"
            se = sour_enemy(mx, feet, enemies, walls, frozenset(self.cleared), box, rear=self.k.REAR_SOUR)
            lvl = 0.0
            if se is not None:
                lvl = self.k.SOUR_GAIN * se.theta
                sig = self.k.SENSOR_NOISE if self.rng is not None else 0.0
                if sig > 0:
                    lvl *= 1.0 + sig * self.rng.standard_normal()
            I[self.m["DC4_L"]] = I[self.m["DC4_R"]] = lvl
            lm.extra.update(sour_box=None if se is None else (se.x, se.top, se.w, se.h), sour_theta=0.0 if se is None else se.theta, sour_level=lvl)
            if self.k.REAR_SOUR:
                lm.extra["sour_rear"] = bool(se is not None and se.rear)
        if self.k.HUM_SENSE:
            assert "JO" in self.m, "HUM_SENSE needs the JO brain (W_steer_jo.npy)"
            hb = hum_block(mx, feet, level.scan_blocks(ram), box, reach=self.k.HUM_REACH_PX, eye_dy=self.k.EYE_DY)
            level_in = self.k.HUM_GAIN * theta_of(hb[2], level.TILE) if hb else 0.0
            I[self.m["JO"]] = level_in
            lm.extra.update(hum_block=None if hb is None else (hb[0], hb[1], hb[2]), hum_level=level_in, jo_input=level_in)
        if self.k.SMELL_SENSE:
            assert "ORN_L" in self.m, "SMELL_SENSE needs the ORN brain (W_steer_jo_orn.npy)"
            mush = mushroom(ram)
            lvl_l = lvl_r = 0.0
            sbox = None
            if mush is not None:
                mxm, ytop = mush
                d = float(np.hypot(mx + box[0] - (mxm + 8), (feet - box[1] + self.k.EYE_DY) - (ytop + 8)))
                lvl = self.k.SMELL_GAIN * theta_of(d, 16)
                sig = self.k.SENSOR_NOISE if self.rng is not None else 0.0
                if sig > 0:
                    lvl *= 1.0 + sig * self.rng.standard_normal()
                if mxm + 8 < mx + box[0] / 2:              # left of Mario's centre -> the left antenna
                    lvl_l = lvl
                else:
                    lvl_r = lvl
                sbox = (mxm, ytop, 16, 16)
            I[self.m["ORN_L"]], I[self.m["ORN_R"]] = lvl_l, lvl_r
            lm.extra.update(smell_box=sbox, smell_L=lvl_l, smell_R=lvl_r)
        return I, lm

    def from_threat(self, t):
        if t is None:
            th, dth, ident, d, src = 0.0, 0.0, None, None, "none"
        else:
            th, ident, d, src = t.theta, t.ident, t.d, t.kind
            dth = abs(th - self.prev_theta) if ident == self.prev_id else 0.0     # 0 at a target switch
        v_rel = np.nan if (t is None or ident != self.prev_id or self.prev_d is None) else float(self.prev_d - d)
        tau = d / v_rel if (d is not None and np.isfinite(v_rel) and v_rel > 0.05) else np.nan
        self.prev_id, self.prev_theta, self.prev_d = ident, th, d
        I = np.zeros(self.K)
        sig = self.k.SENSOR_NOISE if self.rng is not None else 0.0
        th_factor = 1.0
        for name, val in (("LC4_R", dth), ("LPLC2_R", th)):
            idx = self.m[name]
            n = int(idx.sum()) if self.k.NOISE_MODE == "neuron" else 1
            noise = 1.0 + sig * self.rng.standard_normal(n) if sig > 0 else 1.0
            if name == "LPLC2_R":
                th_factor = float(np.mean(noise))
            I[idx] = val * noise
        I[self.m["LC10a_R"]] = self.k.HOME_R if self.k.HOME_SENSE else 0.0
        lm = Loom(th, dth, tau, src, d, th * th_factor)
        lm.extra = dict(threat_kind=src, threat_id="" if ident is None else f"{ident[0]}:{ident[1]}",
                        box=None if t is None else (t.x, t.top, t.w, t.h), base=None if t is None else t.base, rims=None if t is None else t.rims)
        if self.k.REAR_EYE:
            lm.extra["threat_rear"] = bool(t is not None and t.rear)
        return I, lm
