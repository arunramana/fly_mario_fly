"""How far can a jump lift Mario's head before a ceiling stops it?

The ceilings are the terrain boxes of the frame (pipes, stairs, bricks, ? blocks, used blocks). A terrain box
counts when at least one of its 16-px tile rows lies wholly above the head, as the tile scan of the old code did:
the ceiling is then the underside of the lowest such tile in any column of the span.
"""
from __future__ import annotations

from fly_mario.senses.kit.world import kind_of


def rise_available(world, facts, x0: float, x1: float, feet: float, box_h: float) -> float:
    """Pixels the head can rise above its resting height over the columns [x0, x1), capped at a full jump."""
    t = facts["grid"]["tile"]
    cap = facts["mario"]["jump_apex"]
    head = feet - box_h
    aligned = (head // t) * t               # the row boundary at or above the head: tiles must end here or higher
    left = (x0 // t) * t
    ceil = 0.0
    for o in world:
        b = o.box
        if kind_of(o.type) != "terrain" or not (b.x < x1 and b.x + b.w > left):
            continue
        if b.y + t <= aligned:              # one of its tile rows is wholly above the head
            ceil = max(ceil, min(b.y + b.h, aligned))
    return max(0.0, min(float(cap), head - ceil))
