"""Jump: the jump muscle motor neuron (TTMn) holds A. The fly holds the button, the code does not.

Press: Mario is on the ground, TTMn >= jump.ttmn_thresh, A not already down. Hold: A stays down while
TTMn >= jump.release_thresh (a lower bar, so a jump is not chopped by a flicker). Release: TTMn below it. On the
frame Mario lands A is up for exactly one frame (the game needs a release before it accepts a new jump); the press
rule applies again from the next frame. No hold timer, no cooldown.

`state` is this action's own dict, kept from frame to frame; the runner sets state["airborne"] each frame.
"""
from fly_mario.contracts import ButtonIntent, KnobSpec


class Jump:
    name = "jump"
    label = "Jump"
    button = "A"
    source_groups = ["TTMn"]
    reads = []
    priority = 0
    knobs = [
        KnobSpec("jump.ttmn_thresh", "Press A when TTMn is above", "jumpy", "only when sure", 0.10, 0.06374, 0.1912,
                 origin="invented", evolvable=True),
        # Original dial = the old hand-set RELEASE_THRESH = TTMN_THRESH (0.10, i.e. no hysteresis).
        # 0.0978 was the E1-evolved value, so it belongs in the tuned flies' yaml, not here.
        KnobSpec("jump.release_thresh", "Keep A down while TTMn is above", "lets go early", "holds long", 0.10,
                 0.04889, 0.1467, origin="invented", evolvable=True),
    ]

    def decide(self, rates, knobs, state):
        ttmn = rates.get("TTMn", 0.0)
        air = bool(state.get("airborne", False))
        landing = state.get("prev_air", False) and not air
        state["prev_air"] = air
        down = state.get("down", False)
        state["why"] = ""
        if landing:
            if down:
                state["why"] = "landing_reset"
            state["down"] = False
            press = False
        elif down:
            press = ttmn >= knobs["jump.release_thresh"]
            if not press:
                state["why"] = "loom_faded"
            state["down"] = press
        elif not air and ttmn >= knobs["jump.ttmn_thresh"]:
            state["down"] = press = True
        else:
            press = False
        if press:
            return ButtonIntent(press=frozenset({"A"}), priority=self.priority)
        return ButtonIntent(release=frozenset({"A"}), priority=self.priority)


PLUGIN = Jump()
