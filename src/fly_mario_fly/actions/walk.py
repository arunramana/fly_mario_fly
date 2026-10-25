"""Walk: forward walking neurons (DNp09) above a threshold hold Right.

Buttons are the env's names (right, left, A, B...). The lowest priority: steering and backing up both override it.
"""
from fly_mario_fly.contracts import ButtonIntent, KnobSpec
from fly_mario_fly.rules import Route, declare


class Walk:
    name = "walk"
    label = "Walk"
    button = "right"
    source_groups = ["DNp09"]
    reads = []
    priority = 0
    knobs = [
        KnobSpec("walk.thresh", "Walk when DNp09 is above", "easily", "only when strong", 0.05, 0.01, 0.2,
                 origin="invented", evolvable=False),
    ]

    def decide(self, rates, knobs, state):
        if rates.get("DNp09", 0.0) >= knobs["walk.thresh"]:
            return ButtonIntent(press=frozenset({"right"}), priority=self.priority)
        return ButtonIntent(priority=self.priority)


PLUGIN = Walk()


DECLARATION = declare(
    "action", "invented",
    "Invented readout: Right is held while the real forward-walking neurons (DNp09) are above a threshold we chose.",
    route=Route("walking", ("DNp09",), "LC10a -> DNp09 (forward walking)"),
    reads_groups=("DNp09",), buttons=("right",))
