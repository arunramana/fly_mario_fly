"""Steer: the steering neurons (DNa01/02). Right side more active than left by more than the threshold -> Right;
left more active -> Left, and Left also lets go of Right (you cannot hold both).

Overrides walk (higher priority); backing up overrides it in turn.
"""
from fly_mario_fly.contracts import ButtonIntent, KnobSpec
from fly_mario_fly.rules import Route, declare


class Steer:
    name = "steer"
    label = "Steer"
    button = "left/right"
    source_groups = ["DNa_L", "DNa_R"]
    reads = []
    priority = 1
    knobs = [
        KnobSpec("steer.thresh", "Steer when |DNa right - left| is above", "twitchy", "only when clear", 0.01, 0.005067, 0.0152,
                 origin="invented", evolvable=True),
    ]

    def decide(self, rates, knobs, state):
        steer = rates.get("DNa_R", 0.0) - rates.get("DNa_L", 0.0)
        t = knobs["steer.thresh"]
        if steer < -t:
            return ButtonIntent(press=frozenset({"left"}), release=frozenset({"right"}), priority=self.priority)
        if steer > t:
            return ButtonIntent(press=frozenset({"right"}), priority=self.priority)
        return ButtonIntent(priority=self.priority)


PLUGIN = Steer()


DECLARATION = declare(
    "action", "invented",
    "Invented readout: Left or Right is held when the real steering neurons (DNa01/02) differ by more than a threshold we chose.",
    route=Route("walking", ("DNa01", "DNa02"), "LC10a -> DNa01/02 (steering)"),
    reads_groups=("DNa_L", "DNa_R"), buttons=("left", "right"))
