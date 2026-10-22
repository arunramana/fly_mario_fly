"""A hole has no face to loom, so it gets a tower: the upright of an inverted L whose bar is the hole at the level Mario takes off from."""
from fly_mario.contracts import Box, KnobSpec


class FarEdgeTower:
    name = "far_edge_tower"
    label = "Tower on the far edge"
    description = ("For a pit: a 16 px wide tower on the far edge, standing on the hole's bar at the level Mario takes off from. "
                   "Height = min(the pit's width, a full jump) + how far the far rim's top is above that level, so its top is "
                   "always above the far rim.")
    knobs = [
        KnobSpec("shape.tower.pos", "Where the tower stands", "near edge", "far edge", 1.0, 0.0, 1.0,
                 origin="invented", evolvable=True),
        KnobSpec("shape.tower.h", "Tower height", "short", "tall", 1.0, 0.25, 2.0,
                 origin="invented", evolvable=True),
    ]
    family = "tower"

    def shape(self, obj, facts, knobs):
        b, t = obj.box, facts["grid"]["tile"]
        pos = knobs.get("shape.tower.pos", 1.0)
        mul = knobs.get("shape.tower.h", 1.0)
        near_y, far_y = obj.state.get("loom_rims", (b.y, b.y))      # rim tops, from the pit finder; without them: the hole's own top
        height = max(1.0, min(b.w, facts["mario"]["jump_apex"]) * mul) + max(0.0, near_y - far_y)
        x = b.x + b.w if pos == 1.0 else b.x + int(round(pos * b.w))
        return Box(x, near_y - height, t, height)


PLUGIN = FarEdgeTower()
