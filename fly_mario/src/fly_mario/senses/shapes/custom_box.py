"""A box the user shapes by hand: shift and scale the object's own box."""
from fly_mario.contracts import Box, KnobSpec


class CustomBox:
    name = "custom_box"
    label = "Custom box"
    description = "The object's box shifted by (dx, dy) px and scaled in width and height: for trying what the fly would do."
    knobs = [
        KnobSpec("shape.custom.dx", "Shift right", "left", "right", 0.0, -32.0, 32.0, origin="invented", evolvable=True),
        KnobSpec("shape.custom.dy", "Shift down", "up", "down", 0.0, -32.0, 32.0, origin="invented", evolvable=True),
        KnobSpec("shape.custom.w", "Width scale", "narrower", "wider", 1.0, 0.25, 4.0, scale="log", origin="invented", evolvable=True),
        KnobSpec("shape.custom.h", "Height scale", "shorter", "taller", 1.0, 0.25, 4.0, scale="log", origin="invented", evolvable=True),
    ]
    family = "free"

    def shape(self, obj, facts, knobs):
        b = obj.box
        return Box(b.x + knobs.get("shape.custom.dx", 0.0), b.y + knobs.get("shape.custom.dy", 0.0),
                   max(1.0, b.w * knobs.get("shape.custom.w", 1.0)), max(1.0, b.h * knobs.get("shape.custom.h", 1.0)))


PLUGIN = CustomBox()
