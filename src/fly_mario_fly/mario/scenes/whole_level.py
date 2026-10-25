"""The level exactly as the game plays it."""

from fly_mario_fly.rules import declare


class WholeLevel:
    name = "whole_level"
    label = "Whole level"
    description = "Nothing changed: every enemy, pipe and pit as in the game."
    params: list = []

    def on_reset(self, env, p):
        pass

    def on_frame(self, env, p):
        pass


PLUGIN = WholeLevel()


DECLARATION = declare("scene", "invented",
    "A test-scene edit of the running game (ours). Nothing changed: every enemy, pipe and pit as in the game.")
