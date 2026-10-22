"""Terrain only: every enemy is switched off, every frame. Lifts and moving platforms share the enemy slots but are not enemies."""
from fly_mario.mario import ram as R


class NoEnemies:
    name = "no_enemies"
    label = "No enemies"
    description = ("Switches off every enemy slot each frame (also ones that spawn as the screen scrolls); "
                   "lifts and moving platforms stay.")
    params: list = []

    def on_reset(self, env, p):
        R.sweep_enemies(env, env.facts, env.facts["objects"]["non_enemy"]["types"])

    def on_frame(self, env, p):
        R.sweep_enemies(env, env.facts, env.facts["objects"]["non_enemy"]["types"])


PLUGIN = NoEnemies()
