"""Looming: the next threat, as the fly's eye would see it grow. Feeds the escape circuit (LC4 / LPLC2 -> Giant Fiber).

Invariant 1 of the project: the NES view is side-on, so nothing "expands" on the screen. The angle is synthesised
from RAM, as seen from Mario's eye:  theta = 2*atan(h / 2d)  with d the true 2-D gap between Mario's box and the
object's box. ONE object feeds the detectors at a time (the nearest by gap, re-chosen every frame): LPLC2 gets
theta, LC4 gets |change of theta| (it answers motion, not size), and a switch of target gives a change of 0.

What counts as "the object" depends on the loom shape of its type (senses/shapes/):
  free   (own_box, custom_box)  a creature or pickup: the box itself. Once Mario's feet are above its top with his
                                body over it he has got past it; it drops out until he lands ("cleared"), and the
                                next threat takes over.
  wall   (solid_block)          a wall standing on the floor looms from the ground Mario TOOK OFF from up to its top
                                (in the air his head is already up and the angle would flicker). Only the nearest
                                wall that still rises above him is a candidate. Its height is zero once he stands
                                above it.
  tower  (far_edge_tower)       a pit: the tower on its far edge looms like a wall, but while the pit is still ahead
                                it keeps competing with its base (the hole), so an already-released pit holds the
                                channel at zero (dashed) instead of letting a farther threat through. Released
                                mid-jump, it stays released until landing. The pit is an inverted L: a bar (the hole) one tile
                                row below the level Mario takes off from, and the tower on its far end.

Toggles read from the whole-fly senses that run before this one (see headroom.py and rear_eye.py): the headroom
factor scales a creature's angle by min(1, rise / (height + clearance)); the rear eye also lets an enemy BEHIND
Mario compete while its gap is shrinking.

EYES: only the RIGHT-eye detectors (LC4_R, LPLC2_R: 146 of the 311) are driven, because Mario faces right and the
threats come from the right. This is an explicit knob (loom.eyes); 1 drives both eyes alike.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from typing import Optional

from fly_mario import registry
from fly_mario.contracts import KnobSpec, SenseOutput
from fly_mario.senses.kit import draw
from fly_mario.senses.kit.geom import eye_of, feet_of, gap, identity, is_behind, is_cleared, over, theta_of
from fly_mario.senses.kit.headroom import rise_available
from fly_mario.senses.kit.world import default_shapes, floor_y, hole_box, standing_walls, top_of_wall_at


# Which hole ranks a pit against the other threats. False: the floor row, as the frozen 1-1 champion saw it (the golden
# episodes pass). True: the bar at the take-off level; on 1-1's brick row above the gap at x=2448 that makes all 10 holdout
# runs die at x~2469 (see the lane report), so it stays off until the champion is re-frozen.
HOLE_DISTANCE_FROM_TAKEOFF = False


@dataclass
class _Cand:
    family: str                 # free / wall / tower
    obj: object
    ident: tuple
    x: float
    top: float
    w: float
    h: float                    # the height that sets theta
    vis: tuple                  # the box to draw
    base: Optional[tuple] = None    # towers: the hole, the bar of the inverted L, drawn at the take-off level
    sel_base: Optional[tuple] = None    # towers: the box whose distance ranks the pit against the other threats
    rims: Optional[tuple] = None
    d: float = 0.0
    dsel: float = 0.0
    theta: float = 0.0
    rear: bool = False


@lru_cache(maxsize=1)
def _shapes() -> dict:
    return registry.list_plugins("shapes")


def _order(obj):
    """A stable order for ties: the game's own slot number when there is one."""
    return obj.state.get("slot", obj.id)


class Looming:
    name = "looming"
    label = "Looming (the next threat grows)"
    effect = "An object ahead grows in the fly's eye; if it grows fast enough the Giant Fiber fires and Mario jumps."
    scope = "per_object"
    colour = draw.RED
    line = "solid"
    feeds = ["escape"]
    order = 10
    raises = []
    reads = ["rear_eye", "headroom", "headroom_clearance"]
    DTHETA_NORM = 0.5              # a change of theta this big (rad per frame) fills the "to LC4" bar
    knobs = [
        KnobSpec("loom.eyes", "Eyes used", "right eye only", "both eyes", 0.0, 0.0, 1.0,
                 origin="invented", evolvable=False, kind="switch"),
        KnobSpec("loom.pit_gain", "Pit tower strength", "faint", "strong", 1.0, 0.1, 4.0, scale="log",
                 origin="invented", evolvable=False),
    ]

    def cue(self, objects, mario, facts, knobs, memory):
        mem = memory
        shapes, defaults = _shapes(), default_shapes()
        tile, floor = facts["grid"]["tile"], floor_y(facts)
        feet, box_w = feet_of(mario), mario.w
        if not mario.airborne or mem.get("ground") is None:
            mem["ground"] = feet                            # the ground he last stood on = the take-off ground in the air
        ground = mem["ground"]
        released, cleared = mem.setdefault("released", set()), mem.setdefault("cleared", set())
        if not mario.airborne:
            released.clear()
            cleared.clear()

        free, walls, towers = [], [], []
        wall_boxes = None
        for obj in sorted(objects, key=_order):
            sh = shapes[obj.state.get("loom_shape") or defaults.get(obj.type, "own_box")]
            if sh.family == "tower":
                if "rims" in obj.state:                     # the pit finder measured them from where Mario walks
                    rims = obj.state["rims"]
                else:                                       # a pit made by hand (tests): look the wall tops up
                    if wall_boxes is None:
                        wall_boxes = standing_walls(mem.world, facts)
                    b0 = obj.box
                    rims = (top_of_wall_at(wall_boxes, b0.x - tile, facts), top_of_wall_at(wall_boxes, b0.x + b0.w, facts))
                obj = replace(obj, state={**obj.state, "loom_rims": rims})
            box = sh.shape(obj, facts, knobs)
            family = sh.family
            if family == "wall" and box.y + box.h != floor:
                family = "free"                             # a block in the air is not a wall
            {"free": free, "wall": walls, "tower": towers}[family].append((obj, box))

        # --- creatures and pickups -----------------------------------------------------------
        if mario.airborne:
            cleared |= {identity(o) for o, b in free if is_cleared(mario, b.y, b.x, b.x + b.w)}
        closing = frozenset()
        if mem.mods.get("rear_eye"):
            # A looming detector answers an EXPANDING object: one behind Mario counts only while its gap shrinks.
            now = {identity(o): gap(mario, b.x, b.y, b.w, b.h, rear=True) for o, b in free if is_behind(mario, b.x, b.w)}
            before = mem.get("rear_gap", {})
            closing = frozenset(i for i, d in now.items() if i in before and d < before[i])
            mem["rear_gap"] = now
        cands = []
        for o, b in free:
            ident = identity(o)
            if ident in cleared or is_cleared(mario, b.y, b.x, b.x + b.w):
                continue
            cands.append(_Cand("free", o, ident, b.x, b.y, b.w, b.h, (b.x, b.y, b.w, b.h)))
        free_cands = list(cands)

        # --- the nearest wall that still rises above him ---------------------------------------
        for o, b in sorted(walls, key=lambda ob: ob[1].x):
            if b.x + b.w <= mario.x:
                continue                                    # fully behind his left edge
            h = 0.0 if is_cleared(mario, b.y, b.x, b.x + b.w) else ground - b.y
            if h > 0:
                cands.append(_Cand("wall", o, identity(o), b.x, b.y, b.w, h, (b.x, b.y, b.w, h)))
                break                                       # later walls are behind this one

        # --- pits ---------------------------------------------------------------------------
        for o, b in towers:
            px, pw = o.box.x, o.box.w
            if mario.x >= px + pw:
                continue                                    # his body is past the far edge: the pit is over
            ident = identity(o)
            h = 0.0 if (ident in released or is_cleared(mario, b.y, b.x, b.x + b.w)) else ground - b.y
            near_y, far_y = o.state["loom_rims"]
            cands.append(_Cand("tower", o, ident, b.x, b.y, b.w, max(h, 0.0), (b.x, b.y, b.w, b.h),
                               base=hole_box(o.box, near_y, facts), sel_base=hole_box(o.box, near_y, facts) if HOLE_DISTANCE_FROM_TAKEOFF else (px, floor, pw, tile), rims=(near_y, far_y, px - tile, px + pw)))

        ahead = [c for c in cands if c.x >= mario.x or c.family == "tower" or over(mario, c.x, c.x + c.w)]
        pit_gain = knobs.get("loom.pit_gain", 1.0)
        for c in ahead:
            c.d = gap(mario, c.x, c.top, c.w, c.h)
            c.dsel = gap(mario, *c.sel_base) if c.sel_base else c.d    # a pit competes with the others by its nearest part, the hole
            if c.family == "tower":
                c.theta = pit_gain * theta_of(c.d, c.h) if c.h > 0 else 0.0
            else:
                c.theta = theta_of(c.d, c.h)
        for c in free_cands:
            if c.ident in closing and is_behind(mario, c.x, c.w):
                c.rear = True
                c.d = c.dsel = gap(mario, c.x, c.top, c.w, c.h, rear=True)
                c.theta = theta_of(c.d, c.h)
                ahead.append(c)
        t = min(ahead, key=lambda c: c.dsel) if ahead else None
        if t is not None and t.family == "tower" and t.h == 0 and mario.airborne:
            released.add(t.ident)

        # --- headroom: a creature you cannot jump over does not loom as much ----------------------
        hf, rise, need, raw = 1.0, 0.0, 0.0, None
        if mem.mods.get("headroom") and t is not None and t.family == "free":
            x0, x1 = (t.x, mario.x + box_w) if t.rear else (mario.x, max(t.x + t.w, mario.x + box_w))
            rise = rise_available(mem.world, facts, x0, x1, ground, mario.h)
            need = t.h + mem.mods.get("headroom_clearance", 2.0)
            hf = min(1.0, rise / max(need, 1e-9))
            raw, t.theta = t.theta, t.theta * hf

        # --- what the detectors get ---------------------------------------------------------------
        if t is None:
            th, dth = 0.0, 0.0
        else:
            th = t.theta
            dth = abs(th - mem.get("prev_theta", 0.0)) if t.ident == mem.get("prev_id") else 0.0     # 0 at a target switch
        mem["prev_id"], mem["prev_theta"] = (None if t is None else t.ident), th
        lc4, lplc2 = dth * memory.noise(), th * memory.noise()           # one noise draw per detector population
        inputs = {"LC4_R": lc4, "LPLC2_R": lplc2}
        if knobs.get("loom.eyes", 0.0) >= 0.5:
            inputs.update(LC4_L=lc4, LPLC2_L=lplc2)

        steps = [
            draw.step("distance", "gap = hypot(gap_x, gap_y)", 0.0 if t is None else t.d, 0.0 if t is None else t.d / facts["grid"]["screen_w"]),
            draw.step("height", "h of the object", 0.0 if t is None else t.h, 0.0 if t is None else t.h / facts["mario"]["jump_apex"]),
            draw.step("angle", "theta = 2*atan(h / 2d)", 0.0 if t is None else (raw if raw is not None else t.theta), None, "LPLC2_R"),
            draw.step("headroom", "min(1, rise / (h + clearance))", hf, hf),
            draw.step("to LPLC2", "theta used", th, th / 3.141592653589793, "LPLC2_R"),
            draw.step("to LC4", "|change of theta|", dth, dth / self.DTHETA_NORM, "LC4_R"),
        ]
        overlay = []
        if t is not None:
            line = "dashed" if (th <= 0.0 or hf < 1.0) else "solid"
            x, y, w, h = t.vis
            overlay.append(draw.box(x, y, w, h, draw.RED, line))
            overlay.append(draw.wedge(eye_of(mario), x, y, w, h, draw.RED, line))
            if t.base:
                overlay.append(draw.box(*t.base, draw.RED, "dotted"))
        return SenseOutput(inputs=inputs, overlay=overlay, steps=steps)


PLUGIN = Looming()
