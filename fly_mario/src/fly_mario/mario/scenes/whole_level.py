"""The level exactly as the game plays it."""


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
