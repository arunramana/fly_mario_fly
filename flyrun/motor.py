"""Brain state -> one button combo (nb 09/14 jump, nb 19 walk, nb 20 steer)."""
from dataclasses import dataclass

from . import env as E


@dataclass
class Muscle:
    a_left: int = 0      # frames of A still to hold
    cool_left: int = 0   # frames of refractory after a hold during which A cannot start

    def press(self, trigger, knobs):
        """A hold + cooldown (nb 14): trigger starts A for A_HOLD frames, then COOLDOWN frames refused."""
        if self.a_left > 0:
            a = True
            self.a_left -= 1
            if self.a_left == 0:
                self.cool_left = knobs.COOLDOWN
        elif self.cool_left > 0:
            a = False
            self.cool_left -= 1
        elif trigger:
            a = True
            self.a_left = knobs.A_HOLD - 1
            if self.a_left == 0:
                self.cool_left = knobs.COOLDOWN
        else:
            a = False
        return a


@dataclass
class Muscle2:
    """Motor v2 (Part S2): the fly holds the jump. No hold counter, no cooldown.
    press: grounded AND TTMn >= TTMN_THRESH AND A not already down. hold: A stays down while TTMn >= RELEASE_THRESH.
    release: TTMn < RELEASE_THRESH. landing reset: on the airborne -> grounded transition A is up for exactly this one frame
    (SMB needs a release before a new jump); the press rule applies again from the next frame."""
    down: bool = False
    prev_air: bool = False
    why: str = ""        # why A is up this frame if it was released: "loom_faded" | "landing_reset" | ""

    def step(self, ttmn, thr, rel, airborne):
        self.why = ""
        landing = self.prev_air and not airborne
        self.prev_air = airborne
        if landing:
            if self.down:
                self.why = "landing_reset"
            self.down = False
            return False
        if self.down:
            if ttmn >= rel:
                return True
            self.down, self.why = False, "loom_faded"
            return False
        if (not airborne) and ttmn >= thr:
            self.down = True
            return True
        return False


def decide(h, masks, knobs, m, airborne=False):
    """-> (action index, readouts dict). `m` is a Muscle, updated in place.

    A hold + cooldown as in nb 14: TTMn >= thresh starts A for A_HOLD frames, then COOLDOWN
    frames of refusal. (A MUSCLE_DECAY trace was tried in part 2 and failed -- see runs/001_senses.md --
    because TTMn keeps rising as the face nears, so the trace never drops and A is never released.)
    DNp09 >= thresh means walk Right (nb 19). steer = mean(DNa_R) - mean(DNa_L);
    Left wins when steer < -thresh (nb 20). No B button (not in our list).
    """
    ttmn = float(h[masks["TTMn"]].mean())
    dnp09 = float(h[masks["DNp09"]].mean())
    steer = float(h[masks["DNa_R"]].mean() - h[masks["DNa_L"]].mean())

    if knobs.MOTOR_VERSION == "v2":
        rel = knobs.TTMN_THRESH if knobs.RELEASE_THRESH is None else knobs.RELEASE_THRESH
        a = m.step(ttmn, knobs.TTMN_THRESH, rel, airborne)
    else:
        a = m.press(ttmn >= knobs.TTMN_THRESH, knobs)

    walk = dnp09 >= knobs.DNP09_THRESH
    go_left = steer < -knobs.STEER_THRESH
    go_right = (walk or steer > knobs.STEER_THRESH) and not go_left
    if go_left:
        action = E.LEFT_A if a else E.LEFT
    elif go_right:
        action = E.RIGHT_A if a else E.RIGHT
    else:
        action = E.NOOP   # a held A with no direction is dropped: our list has no bare A
    out = dict(ttmn=ttmn, dnp09=dnp09, steer=steer)
    if knobs.MOTOR_VERSION == "v2":
        out["why"] = m.why
    return action, out
