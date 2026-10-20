"""Pit: a run of columns ahead with no support. Terrain.

Measured from where Mario walks, not from the bottom of the screen: a column's support is the top of the highest solid
tile at or below the ground he took off from (ram.support_top). A column is a gap when its support is missing. Solid is the game's own collision rule (facts["collision"]); everything else is a gap, so
empty air, lava and water need no code, only facts."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class Pit:
    name = "pit"
    label = "Pit"
    note = ("A gap in what Mario can stand on. state: open (runs off the right screen edge, width is a lower bound), "
            "rims (near rim top y, far rim top y), ground (take-off ground y), too_wide, lift_near.")
    kind = "terrain"
    default_loom_shape = "far_edge_tower"
    block_hit_tile = None
    causes_fall_death = True            # Mario dying beside one of these (within its box +- 12 px) fell in

    def find(self, ram, facts):
        g = facts["grid"]
        t = g["tile"]
        ground = R.takeoff_ground(ram, facts)
        sup = {wx: R.support_top(ram, facts, wx, ground) for wx in R.visible_columns(ram, facts)}
        # A gap is a column with nothing to stand on at or below the take-off ground. (The brief also says "or more than one
        # tile below it". In SMB's 13-row buffer that only ever bites when Mario stands high, and then it turns the floor
        # beside every pipe and every stair step into a "pit", so a lower floor or ledge, however deep, is a fall, not a pit.)
        gap = lambda wx: sup[wx] is None                                       # noqa: E731
        runs, cur = [], None
        for wx in sup:
            if gap(wx):
                cur = [wx, t] if cur is None else [cur[0], cur[1] + t]
            elif cur is not None:
                runs.append((cur, False))
                cur = None
        if cur is not None:
            runs.append((cur, True))
        lifts = [x for _, typ, _, x, _ in R.active_slots(ram, facts) if typ in facts["objects"]["lift"]["types"]]
        out = []
        for (x, w), is_open in runs:
            near = R.support_top(ram, facts, x - t, ground) if x - t >= 0 else None
            near = ground if near is None else near
            far = near if is_open else sup[x + w]            # an open pit has no far rim on screen yet: assume level with the near one
            reach = facts["mario"]["jump_reach"]
            lift = facts["objects"]["lift"]["near_px"]
            # The box stays the hole's two floor rows (as before): headroom reads terrain boxes as ceilings and the sense ranks
            # the hole by it. What is measured from where Mario walks is the rims (state), hence the tower.
            out.append(R.instance("pit", x, Box(x, g["ground_row"] * t, w, 2 * t), ram, facts, open=is_open, rims=(near, far), ground=ground,
                                  too_wide=w >= reach, lift_near=any(x - lift <= lx <= x + w + lift for lx in lifts)))
        return out

    def remove(self, env):
        pass


PLUGIN = Pit()
