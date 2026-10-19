"""A hole has no face to loom, so it gets a tower: 16 px wide on its far edge, as tall as the jump needs to be."""
from fly_mario.contracts import Box, KnobSpec


class FarEdgeTower:
    name = "far_edge_tower"
    label = "Tower on the far edge"
    description = ("For a pit: a 16 px wide tower standing on the far edge, height = min(the pit's width, a full jump), "
                   "its base on the highest rim of the pit (a pipe or stair column beside it, else the floor).")
    knobs = [
        KnobSpec("shape.tower.pos", "Where the tower stands", "near edge", "far edge", 1.0, 0.0, 1.0,
                 origin="invented", evolvable=True),
        KnobSpec("shape.tower.h", "Tower height", "short", "tall", 1.0, 0.25, 2.0,
                 origin="invented", evolvable=True),
    ]
    handles = ["pit"]
    family = "tower"

    def shape(self, obj, facts, knobs):
        b, t = obj.box, facts["grid"]["tile"]
        pos = knobs.get("shape.tower.pos", 1.0)
        mul = knobs.get("shape.tower.h", 1.0)
        height = max(1.0, min(b.w, facts["mario"]["jump_apex"]) * mul)
        near_y, far_y = obj.state.get("loom_rims", (b.y, b.y))      # the sense looks the rims up; without them: the hole's own top
        x = b.x + b.w if pos == 1.0 else b.x + int(round(pos * b.w))
        return Box(x, min(near_y, far_y) - height, t, height)


PLUGIN = FarEdgeTower()
