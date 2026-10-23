"""Start at a given x: a scripted walker carries Mario there with the enemies off, then the game is handed back."""
from fly_mario_fly.mario import walker


class StartAtX:
    name = "start_at_x"
    label = "Start at x"
    description = ("Walks Mario to world pixel x (jumping walls and pits, enemies off) before the run starts. "
                   "Enemies further on spawn as usual.")
    params = [{"key": "x", "label": "World x in px", "type": "int", "default": 0}]

    def on_reset(self, env, p):
        walker.walk_to(env, int(p["x"]))

    def on_frame(self, env, p):
        pass


PLUGIN = StartAtX()
