"""A solid block: a wall (pipe, stair column) that Mario has to get over."""
from fly_mario.contracts import Box


class SolidBlock:
    name = "solid_block"
    label = "Solid block"
    description = ("The block's own box. One that stands on the floor is a wall: it looms from the ground Mario took "
                   "off from up to its top, and stops looming once his feet are above that top and his body is over it. "
                   "A block floating in the air is just a box.")
    knobs = []
    family = "wall"

    def shape(self, obj, facts, knobs):
        b = obj.box
        return Box(b.x, b.y, b.w, b.h)


PLUGIN = SolidBlock()
