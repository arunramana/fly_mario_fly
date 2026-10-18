"""Senses v2 (Part S1): ONE threat feeds the loom detectors, the nearest one AHEAD by surface-to-surface gap, re-chosen every frame.

Candidates: live enemies (Goomba / Koopa / shell), the nearest wall/pipe/step face that rises above Mario's FEET, and each empty
floor tile ahead (a 16 px pit threat). True 2-D distance d = sqrt(gap_x^2 + gap_y^2) between Mario's box and the object's box;
theta = 2 atan(h / 2d) with the object's height h. dtheta is tracked per object identity: when the chosen object changes,
dtheta is 0 at that frame. Threats behind Mario are ignored; floating blocks do not loom (only level.SOLID_WALL columns do).
Nothing here is read from pixels. The v1 class (senses.Senses) is untouched and stays the default."""
from dataclasses import dataclass

import numpy as np

from . import env as E
from . import level
from .knobs import ENEMY_FEET_OFFSET, ENEMY_TYPES, MARIO_BOX, PIT_GAIN_V2, SIZE_TABLE
from .senses import Loom, theta_of

ADDR_MARIO_Y = 0x00CE      # verified: = Mario's FEET y in tile-buffer coordinates (ground 176 = top of row 11, ledge 112 = top of row 7)
ADDR_ENEMY_Y, ADDR_ENEMY_STATE = 0x00CF, 0x001E
LIVE_STATES = {"goomba": (0, 1), "koopa": (0,), "shell": (2, 3)}   # RAM state bytes; 4 / 0x22 = stomped / defeated -> ignored


@dataclass
class Threat:
    kind: str          # goomba / koopa / shell / face / pit
    ident: tuple       # ("enemy", slot) / ("face", column x) / ("pit", column x)
    x: int             # left edge, world px
    top: int           # top edge y (tile-buffer coordinates)
    w: int
    h: int             # the height that sets theta
    d: float = 0.0     # surface-to-surface 2-D gap (px)
    theta: float = 0.0


def gap(mx, feet, x, top, w, h):
    """2-D gap between Mario's box and an object's box (0 on an axis where they overlap)."""
    mw, mh = MARIO_BOX
    gx = max(0.0, x - (mx + mw))
    gy = max(0.0, top - feet, (feet - mh) - (top + h))   # object entirely below Mario's feet / entirely above his head
    return float(np.hypot(gx, gy))


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


def choose(mx, feet, enemies, walls, pits, enemy_input=True, pipe_sense=True, pit_sense=True, ground=None):
    """-> the chosen Threat (with .d and .theta) or None. walls: [(x, H)] from level.scan_visible, pits: [(x, w)].
    ground = the y of the ground Mario took off from (his current ground while grounded); default = feet (S1 behaviour on the ground)."""
    ground = feet if ground is None else ground
    cands = []
    if enemy_input:
        cands += enemy_boxes(enemies)
    if pipe_sense:
        for wx, H in walls:
            top = level.ROW_GROUND * level.TILE - H            # y of the top of that column
            # S2b (B6/B8): the face's FULL height from the ground he took off from, constant while he rises, and 0 once his
            # feet are above its top (a step, not a slope)
            h = ground - top if feet > top else 0
            if wx >= mx and h > 0:
                cands.append(Threat("face", ("face", wx), wx, top, level.TILE, h))
                break                                           # the nearest rising column ahead; later ones are behind it
    if pit_sense:
        for px, pw in pits:
            for wx in range(px, px + pw, level.TILE):
                if wx + level.TILE > mx:                         # S2b (B9): ahead OR under his footprint; fully behind him = past it
                    cands.append(Threat("pit", ("pit", wx), wx, level.ROW_GROUND * level.TILE, level.TILE, level.TILE))
    ahead = [t for t in cands if t.x >= mx or t.kind == "pit"]
    for t in ahead:
        # a pit tile that overlaps his footprint is directly under him: surface gap 0 (B9), whatever his height above it
        under = t.kind == "pit" and t.x < mx + MARIO_BOX[0]
        t.d = 0.0 if under else gap(mx, feet, t.x, t.top, t.w, t.h)
        t.theta = (PIT_GAIN_V2 if t.kind == "pit" else 1.0) * theta_of(t.d, t.h)
    return min(ahead, key=lambda t: t.d) if ahead else None


class SensesV2:
    def __init__(self, knobs, masks, K, rng=None):
        self.k, self.m, self.K, self.rng = knobs, masks, K, rng
        self.prev_id, self.prev_theta, self.prev_d = None, 0.0, None
        self.ground = None       # y of the ground he last stood on (the take-off ground while airborne)

    def read_ram(self, ram):
        mx = E.mario_x(ram)
        feet = int(ram[ADDR_MARIO_Y])
        enemies = [(s, int(ram[E.ADDR_ENEMY_TYPE + s]), int(ram[ADDR_ENEMY_STATE + s]),
                    int(ram[E.ADDR_ENEMY_PAGE + s]) * 256 + int(ram[E.ADDR_ENEMY_X + s]), int(ram[ADDR_ENEMY_Y + s]))
                   for s in range(E.N_ENEMY_SLOTS) if int(ram[E.ADDR_ENEMY_ACTIVE + s])]
        walls, pits = level.scan_visible(ram)
        return mx, feet, enemies, walls, pits

    def look(self, ram, enemy_input=True):
        """-> (I, Loom). Loom.extra carries the chosen threat for the log / clip."""
        mx, feet, enemies, walls, pits = self.read_ram(ram)
        if int(ram[0x001D]) == 0 or self.ground is None:
            self.ground = feet
        t = choose(mx, feet, enemies, walls, pits, enemy_input, self.k.PIPE_SENSE, self.k.PIT_SENSE, ground=self.ground)
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
                        box=None if t is None else (t.x, t.top, t.w, t.h))
        return I, lm
