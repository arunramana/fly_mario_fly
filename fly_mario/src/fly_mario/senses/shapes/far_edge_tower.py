"""A hole has no face to loom, so it gets a tower: 16 px wide on its far edge, as tall as the jump needs to be."""
from fly_mario.contracts import Box, KnobSpec


class FarEdgeTower:
    name = "far_edge_tower"
    label = "Tower on the far edge"
    description = ("For a pit: a 16 px wide tower standing on the far rim's real top, height = min(the pit's width, a full jump). "
                   "A higher far rim already looms taller, since looming is measured from the take-off ground.")
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
        height = max(1.0, min(b.w, facts["mario"]["jump_apex"]) * mul)
        far_y = obj.state.get("loom_rims", (b.y, b.y))[1]           # the far rim's top y, from the pit finder; without it: the hole's own top
        x = b.x + b.w if pos == 1.0 else b.x + int(round(pos * b.w))
        return Box(x, far_y - height, t, height)


PLUGIN = FarEdgeTower()
