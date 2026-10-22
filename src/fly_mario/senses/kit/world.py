"""Reading the frame as a whole."""
from __future__ import annotations

from functools import lru_cache

from fly_mario import registry


@lru_cache(maxsize=1)
def _kinds() -> dict:
    return {n: p.kind for n, p in registry.list_plugins("objects").items()}


@lru_cache(maxsize=1)
def default_shapes() -> dict:
    """object type name -> the loom shape its plug-in declares."""
    return {n: p.default_loom_shape for n, p in registry.list_plugins("objects").items()}


def kind_of(type_name: str) -> str:
    """enemy / obstacle / pickup / terrain; a type nobody registered counts as an 'obstacle'."""
    return _kinds().get(type_name, "obstacle")


def floor_y(facts) -> float:
    g = facts["grid"]
    return float(g["ground_row"] * g["tile"])


def hole_box(pit_box, takeoff_y: float, facts) -> tuple:
    """(x, y, w, h) of a pit's horizontal bar: the tile row just below the level Mario takes off from, spanning the gap."""
    return (pit_box.x, takeoff_y, pit_box.w, facts["grid"]["tile"])


def standing_walls(world, facts) -> list:
    """Boxes of terrain that stand on the floor (a pipe, a stair column): what a pit's rim is made of."""
    fl = floor_y(facts)
    return [o.box for o in world if kind_of(o.type) == "terrain" and o.box.y + o.box.h == fl]


def top_of_wall_at(walls, x: float, facts) -> float:
    """y of the top of the floor-standing wall covering world x, else the floor itself."""
    for b in walls:
        if b.x <= x < b.x + b.w:
            return b.y
    return floor_y(facts)
