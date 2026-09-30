# What this file does, in plain English:
# Lists every button combination the game can be sent: any mix of right, left,
# down, up, the jump button (A) and the run button (B) -- 64 in all, with the
# original eight first and in their old order so saved action logs still mean
# the same thing. It also turns a direction plus the two button choices (or a
# full set of buttons) into that combination's position in the list.
"""mario/actions/actions.py -- the button-press action space run_steering.py
drives: 8-way, {left,right} x {A on/off} x {B on/off}. run_mario.py has its
own separate 2-action space."""

from __future__ import annotations

MOVES = [
    ["right"], ["right", "B"], ["right", "A"], ["right", "A", "B"],
    ["left"], ["left", "B"], ["left", "A"], ["left", "A", "B"],
]

BUTTONS = ("right", "left", "down", "up", "A", "B")


def _mask(buttons) -> int:
    return sum(1 << BUTTONS.index(b) for b in buttons)


# All 64 combinations of the six buttons. The original 8 keep indices 0-7; the rest follow
# in bit order, the empty press ("NOOP") among them.
_first = {_mask(m) for m in MOVES}
MOVES_ALL = [list(m) for m in MOVES] + [
    [b for b in BUTTONS if mask >> BUTTONS.index(b) & 1] or ["NOOP"]
    for mask in range(64) if mask not in _first]
_INDEX_OF_MASK = {(_mask(m) if m != ["NOOP"] else 0): i for i, m in enumerate(MOVES_ALL)}


def action_from_buttons(right=False, left=False, down=False, up=False, a=False, b=False) -> int:
    """Index into MOVES_ALL of exactly these buttons held (any combination)."""
    mask = sum(1 << i for i, on in enumerate((right, left, down, up, a, b)) if on)
    return _INDEX_OF_MASK[mask]


def buttons_of(action: int) -> dict:
    """{button: held} for an index into MOVES_ALL."""
    held = set(MOVES_ALL[int(action)])
    return {b: b in held for b in BUTTONS}


def action_index(direction: str, press_a: bool, press_b: bool) -> int:
    base = 0 if direction == "R" else 4
    return base + 2 * int(press_a) + int(press_b)
