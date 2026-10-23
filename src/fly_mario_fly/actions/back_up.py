"""Back up: the moonwalker descending neurons (MDN) above a threshold press Left and let go of Right.

The highest priority: it overrides walking and steering. The jump (A) is the jump circuit's and is not affected.
"""
from fly_mario_fly.contracts import ButtonIntent, KnobSpec


class BackUp:
    name = "back_up"
    label = "Back up"
    button = "left"
    source_groups = ["MDN"]
    priority = 2
    reads = []
    knobs = [
        KnobSpec("back_up.mdn_thresh", "Back up when MDN is above", "backs up easily", "only when strong", 0.10, 0.05, 0.15,
                 origin="invented", evolvable=True),
    ]

    def decide(self, rates, knobs, state):
        if rates.get("MDN", 0.0) > knobs["back_up.mdn_thresh"]:
            return ButtonIntent(press=frozenset({"left"}), release=frozenset({"right"}), priority=self.priority)
        return ButtonIntent(priority=self.priority)


PLUGIN = BackUp()
