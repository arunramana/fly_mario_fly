"""ASSISTED / DIAGNOSTIC ONLY: a level-aware scripted player, not the fly.

Used (a) to scroll through 1-1 for the level map and (b) as the pre-takeover prefix of a pit
A/B, the same device as nb 15's scene takeover at x~1037: the script gets Mario to a pit, then
the fly takes over. Any run that uses it says so (driver column = "script").
"""
from . import env as E
from . import level
from .knobs import SCRIPT_HOLD

HOLD = SCRIPT_HOLD   # INVENTED (fixed), knobs.py


class Driver:
    def __init__(self):
        self.hold = 0

    def act(self, ram):
        mx, d = E.nearest_threat_d(ram)
        on_ground = int(ram[0x001D]) == 0
        walls, pits = level.scan_visible(ram)   # raw columns: stair steps are separate walls here
        wall_x = min((x for x, _ in walls if x >= mx), default=None)
        pit_x = min((x for x, _ in pits if x + 1 > mx), default=None)
        near = ((wall_x is not None and wall_x - mx < 28)
                or (pit_x is not None and 0 <= pit_x - mx < 22)
                or (d is not None and d < 30))
        if self.hold == 0 and near and on_ground:
            self.hold = HOLD
        a = E.RIGHT_A if self.hold > 0 else E.RIGHT
        self.hold = max(0, self.hold - 1)
        return a
