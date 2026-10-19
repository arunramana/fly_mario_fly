"""Pit: a run of columns with no ground in either ground row. Terrain."""
from fly_mario.contracts import Box
from fly_mario.mario import ram as R


class Pit:
    name = "pit"
    label = "Pit"
    note = "The hole itself. A pit running off the right edge of the screen has a lower-bound width (state['open'])."
    kind = "terrain"
    default_loom_shape = "far_edge_tower"

    def find(self, ram, facts):
        g = facts["grid"]
        t, row, empty = g["tile"], g["ground_row"], facts["tiles"]["empty"]
        runs, cur = [], None
        for wx in R.visible_columns(ram, facts):
            hole = R.tile(ram, facts, wx, row) == empty and R.tile(ram, facts, wx, row + 1) == empty
            if hole:
                cur = [wx, t] if cur is None else [cur[0], cur[1] + t]
            elif cur is not None:
                runs.append((cur, False))
                cur = None
        if cur is not None:
            runs.append((cur, True))
        return [R.instance("pit", x, Box(x, row * t, w, 2 * t), ram, facts, open=is_open)
                for (x, w), is_open in runs]

    def remove(self, env):
        pass


PLUGIN = Pit()
