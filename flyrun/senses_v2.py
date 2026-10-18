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
from .knobs import ENEMY_FEET_OFFSET, ENEMY_TYPES, MARIO_BOX, MAX_JUMP_HEIGHT, PIT_GAIN_V2, SIZE_TABLE
from .senses import Loom, theta_of

ADDR_MARIO_Y = 0x00CE      # verified: = Mario's FEET y in tile-buffer coordinates (ground 176 = top of row 11, ledge 112 = top of row 7)
ADDR_ENEMY_Y, ADDR_ENEMY_STATE = 0x00CF, 0x001E
LIVE_STATES = {"goomba": (0, 1), "koopa": (0,), "shell": (2, 3)}   # RAM state bytes; 4 / 0x22 = stomped / defeated -> ignored


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


def gap(mx, feet, x, top, w, h):
    """2-D gap between Mario's box and an object's box (0 on an axis where they overlap)."""
    mw, mh = MARIO_BOX
    gx = max(0.0, x - (mx + mw))
    gy = max(0.0, top - feet, (feet - mh) - (top + h))   # object entirely below Mario's feet / entirely above his head
    return float(np.hypot(gx, gy))


def over(mx, x0, x1):
    """His body (MARIO_BOX wide, left edge mx) horizontally overlaps the columns [x0, x1)."""
    return mx < x1 and mx + MARIO_BOX[0] > x0


def merge_columns(walls):
    """[(x, H)] per column -> [(x0, x1, H)]: neighbouring columns of equal height are ONE face (a pipe is 2 columns wide)."""
    out = []
    for wx, H in walls:
        if out and out[-1][1] == wx and out[-1][2] == H:
            out[-1] = (out[-1][0], wx + level.TILE, H)
        else:
            out.append((wx, wx + level.TILE, H))
    return out


def is_cleared(mx, feet, t):
    """S3e: an enemy is cleared when his feet are at or above its top AND his body is over it (the pipe-face / tower test)."""
    return feet <= t.top and over(mx, t.x, t.x + t.w)


def enemy_boxes(enemies):
    """enemies: [(slot, type_byte, state, ex, ey)] -> list of Threat (live, known types only)."""
    out = []
    for slot, typ, state, ex, ey in enemies:
        kind = ENEMY_TYPES.get(typ)
        if kind == "koopa" and state in LIVE_STATES["shell"]:
            kind = "shell"
        if kind is None or state not in LIVE_STATES[kind]:
            continue
        w, h = SIZE_TABLE[kind]
        out.append(Threat(kind, ("enemy", slot), ex, (ey - ENEMY_FEET_OFFSET) - h, w, h))
    return out


def rim_top(walls, x):
    """y of the top of the solid column at world x (tile-aligned): the wall column's top if there is one, else the floor."""
    for wx, H in walls:
        if wx == x:
            return level.ROW_GROUND * level.TILE - H
    return level.ROW_GROUND * level.TILE


def choose(mx, feet, enemies, walls, pits, enemy_input=True, pipe_sense=True, pit_sense=True, ground=None, released=frozenset(), cleared=frozenset()):
    """-> the chosen Threat (with .d and .theta) or None. walls: [(x, H)] from level.scan_visible, pits: [(x, w)].
    ground = the y of the ground Mario took off from (his current ground while grounded); default = feet (S1 behaviour on the ground).
    released = idents of pit towers already released in this jump: their tower stays 0 until the landing (S3c, no re-appearance).
    cleared = idents of enemies already cleared in this jump (S3e): dropped from the candidates until the landing, so the next threat is chosen."""
    ground = feet if ground is None else ground
    cands = []
    if enemy_input:
        cands += [t for t in enemy_boxes(enemies) if t.ident not in cleared and not is_cleared(mx, feet, t)]
    if pipe_sense:
        for x0, x1, H in merge_columns(walls):
            top = level.ROW_GROUND * level.TILE - H            # y of the top of that face
            if x1 <= mx:
                continue                                        # fully behind his left edge
            # S2c (B6): the face keeps its full height from the take-off ground until his feet are above its top AND his body
            # is over its columns; only then it is 0 (a step)
            h = 0 if (feet <= top and over(mx, x0, x1)) else ground - top
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
            top = min(near_y, far_y) - min(pw, MAX_JUMP_HEIGHT)
            tx = px + pw
            h = 0 if (("pit", px) in released or (feet <= top and over(mx, tx, tx + level.TILE))) else ground - top
            t = Threat("pit", ("pit", px), tx, top, level.TILE, max(h, 0))
            t.base = (px, floor, pw, level.TILE)
            t.rims = (near_y, far_y, px - level.TILE, px + pw)     # overlay: the two rim heights and their columns
            cands.append(t)
    ahead = [t for t in cands if t.x >= mx or t.kind == "pit" or over(mx, t.x, t.x + t.w)]
    for t in ahead:
        t.d = gap(mx, feet, t.x, t.top, t.w, t.h)
        t.dsel = gap(mx, feet, *t.base) if t.base else t.d    # a pit competes with other threats by its nearest part (the base)
        t.theta = PIT_GAIN_V2 * theta_of(t.d, t.h) if t.kind == "pit" and t.h > 0 else (0.0 if t.kind == "pit" else theta_of(t.d, t.h))
    return min(ahead, key=lambda t: t.dsel) if ahead else None


class SensesV2:
    def __init__(self, knobs, masks, K, rng=None):
        self.k, self.m, self.K, self.rng = knobs, masks, K, rng
        self.prev_id, self.prev_theta, self.prev_d = None, 0.0, None
        self.ground = None       # y of the ground he last stood on (the take-off ground while airborne)
        self.released = set()    # pit towers released in the current jump (cleared on landing)
        self.cleared = set()     # enemies cleared in the current jump (S3e; emptied on landing)

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
        if int(ram[0x001D]) == 0 or self.ground is None:
            self.ground = feet
        if int(ram[0x001D]) == 0:
            self.released.clear()
            self.cleared.clear()
        else:
            self.cleared |= {t.ident for t in enemy_boxes(enemies) if is_cleared(mx, feet, t)}
        t = choose(mx, feet, enemies, walls, pits, enemy_input, self.k.PIPE_SENSE, self.k.PIT_SENSE, ground=self.ground, released=frozenset(self.released), cleared=frozenset(self.cleared))
        if t is not None and t.kind == "pit" and t.h == 0 and int(ram[0x001D]) != 0:
            self.released.add(t.ident)
        return self.from_threat(t)

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
        I[self.m["LC10a_R"]] = self.k.HOME_R
        lm = Loom(th, dth, tau, src, d, th * th_factor)
        lm.extra = dict(threat_kind=src, threat_id="" if ident is None else f"{ident[0]}:{ident[1]}",
                        box=None if t is None else (t.x, t.top, t.w, t.h), base=None if t is None else t.base, rims=None if t is None else t.rims)
        return I, lm
