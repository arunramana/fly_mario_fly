"""Walk: forward walking neurons (DNp09) above a threshold hold Right.

Buttons are the env's names (right, left, A, B...). The lowest priority: steering and backing up both override it.
"""
from fly_mario.contracts import ButtonIntent, KnobSpec


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
