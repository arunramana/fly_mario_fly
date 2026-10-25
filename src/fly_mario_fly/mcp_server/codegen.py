"""Turn validated numbers and names into a plug-in file. The client never supplies code: every value is checked against a closed
list or a range and embedded with repr(), and no client text goes into a docstring or comment, so a hostile string cannot leave
its literal."""
from __future__ import annotations

import math
import re

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
FLY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_.]{1,60}$")
# The closed recipe lists of senses/kit/templates.py (a test keeps the two in step).
CUES = ("angular_size", "proximity", "constant")
COLOURS = ("red", "green", "yellow", "white")


def check_name(name, what: str = "name") -> str:
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValueError(f"{what} {name!r} must be 2-31 characters: a lowercase letter, then lowercase letters, digits or _")
    return name


def check_text(text, what: str, lo: int = 3, hi: int = 200) -> str:
    if not isinstance(text, str) or not (lo <= len(text.strip()) <= hi) or not text.isprintable():
        raise ValueError(f"{what} must be {lo}-{hi} printable characters on one line")
    return text.strip()


def check_number(x, what: str, lo: float, hi: float) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not (lo <= x <= hi):
        raise ValueError(f"{what} must be a number between {lo:g} and {hi:g}, got {x!r}")
    return float(x)


def check_int_list(xs, what: str, lo: int, hi: int, n_max: int = 16) -> list:
    if not isinstance(xs, (list, tuple)) or not xs or len(xs) > n_max or any(
            isinstance(x, bool) or not isinstance(x, int) or not (lo <= x <= hi) for x in xs):
        raise ValueError(f"{what} must be 1-{n_max} whole numbers between {lo} and {hi}, got {xs!r}")
    return sorted(set(int(x) for x in xs))


def check_names(xs, what: str, n_max: int = 16) -> list:
    if not isinstance(xs, (list, tuple)) or not xs or len(xs) > n_max or any(
            not isinstance(x, str) or not re.match(r"^[A-Za-z0-9_]{1,40}$", x) for x in xs):
        raise ValueError(f"{what} must be 1-{n_max} names (letters, digits, _), got {xs!r}")
    return list(dict.fromkeys(xs))


def _tuple(xs) -> str:
    return "(" + ", ".join(repr(x) for x in xs) + ("," if len(xs) == 1 else "") + ")"


def sense_file(*, name, label, effect, cue, route, drives, gain, colour, range_px, split_by_side, wiring, what, cell_types) -> str:
    return f'''"""A sense written by the MCP server (add_sense) from a fixed recipe. Edit freely."""
from fly_mario_fly.rules import Route, declare
from fly_mario_fly.senses.kit.templates import CueSense

PLUGIN = CueSense(
    name={name!r}, label={label!r}, effect={effect!r},
    cue={cue!r}, feeds=[{route!r}], drives={_tuple(drives)}, gain={gain!r}, colour={colour!r},
    range_px={range_px!r}, split_by_side={split_by_side!r})


DECLARATION = declare(
    "sense", "invented",
    {what!r},
    route=Route({route!r}, {_tuple(cell_types)}, {wiring!r}),
    drives={_tuple(drives)})
'''


def creature_file(*, name, label, note, type_bytes, size, live_states, what) -> str:
    return f'''"""A creature written by the MCP server (add_character) from a fixed recipe. Edit freely."""
from fly_mario_fly.mario.templates import SlotCreature
from fly_mario_fly.rules import declare

PLUGIN = SlotCreature(
    name={name!r}, label={label!r}, note={note!r},
    type_bytes={_tuple(type_bytes)}, size={_tuple(size)}, live_states={_tuple(live_states)})


DECLARATION = declare(
    "character", "invented",
    {what!r})
'''


def terrain_file(*, name, label, note, tile_ids, what) -> str:
    return f'''"""Terrain written by the MCP server (add_object) from a fixed recipe. Edit freely."""
from fly_mario_fly.mario.templates import TileTerrain
from fly_mario_fly.rules import declare

PLUGIN = TileTerrain(
    name={name!r}, label={label!r}, note={note!r}, tile_ids={_tuple(tile_ids)})


DECLARATION = declare(
    "object", "invented",
    {what!r})
'''
