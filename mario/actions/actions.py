"""mario/actions/actions.py -- the button-press action space run_steering.py
drives: 8-way, {left,right} x {A on/off} x {B on/off}. run_mario.py has its
own separate 2-action space."""

from __future__ import annotations

MOVES = [
    ["right"], ["right", "B"], ["right", "A"], ["right", "A", "B"],
    ["left"], ["left", "B"], ["left", "A"], ["left", "A", "B"],
]


def action_index(direction: str, press_a: bool, press_b: bool) -> int:
    base = 0 if direction == "R" else 4
    return base + 2 * int(press_a) + int(press_b)
