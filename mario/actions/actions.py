"""mario/actions/actions.py -- the button-press action space run_steering.py
drives: 8-way, {left,right} x {A on/off} x {B on/off}. Moved verbatim from
run_steering.py (REFACTOR_PLAN.md phase 2) -- run_mario.py's own, much
older 2-action MOVES/RUN/JUMP (its self-contained sprint-001 demo, never
imported by run_steering.py) is left where it is, unrelated to this."""

from __future__ import annotations

MOVES = [
    ["right"], ["right", "B"], ["right", "A"], ["right", "A", "B"],
    ["left"], ["left", "B"], ["left", "A"], ["left", "A", "B"],
]


def action_index(direction: str, press_a: bool, press_b: bool) -> int:
    base = 0 if direction == "R" else 4
    return base + 2 * int(press_a) + int(press_b)
