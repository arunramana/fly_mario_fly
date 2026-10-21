"""Terrain only: every enemy is switched off, every frame."""
from fly_mario.mario import ram as R


class NoEnemies:
    name = "no_enemies"
    label = "No enemies"
    description = "Switches off every enemy slot each frame (also ones that spawn as the screen scrolls)."
    params: list = []

    def on_reset(self, env, p):
        R.sweep_enemies(env, env.facts)

    def on_frame(self, env, p):
        R.sweep_enemies(env, env.facts)


PLUGIN = NoEnemies()
