"""A scripted walker used only to build and test scenes. It is scenery work, not the fly: it carries Mario
through the level, jumping walls and pits, so a scene can start him further on (start_at_x).

Constants come from facts['walker'] (the trigger distances the old scripted driver used)."""
from __future__ import annotations

from fly_mario.mario import ram as R


def _next_wall(ram, facts, mx: int, ids) -> int | None:
    """x of the nearest wall column at or ahead of mx."""
    t = facts["grid"]["tile"]
    xs = [x for x0, x1, _ in R.merged_faces(ram, facts, ids) for x in range(x0, x1, t) if x >= mx]
    return min(xs) if xs else None


def _next_pit(ram, facts, mx: int) -> int | None:
    g = facts["grid"]
    empty = facts["tiles"]["empty"]
    for wx in R.visible_columns(ram, facts):
        if wx + 1 > mx and R.tile(ram, facts, wx, g["ground_row"]) == empty \
                and R.tile(ram, facts, wx, g["ground_row"] + 1) == empty:
            return wx
    return None


class Walker:
    """Holds Right and presses A for a fixed hold when a wall or pit is close (enemies are not its business)."""

    def __init__(self):
        self.hold = 0

    def act(self, env) -> tuple:
        facts, ram = env.facts, env.ram
        w = facts["walker"]
        mx = R.mario_x(ram, facts)
        grounded = int(ram[facts["ram"]["player_state"]]) == 0
        wall = _next_wall(ram, facts, mx, facts["tiles"]["pipe"] + facts["tiles"]["step"])
        pit = _next_pit(ram, facts, mx)
        near = (wall is not None and wall - mx < w["wall_trigger"]) or (pit is not None and 0 <= pit - mx < w["pit_trigger"])
        if self.hold == 0 and near and grounded:
            self.hold = w["jump_hold"]
        buttons = ("right", "A") if self.hold > 0 else ("right",)
        self.hold = max(0, self.hold - 1)
        return buttons


def walk_to(env, x: int) -> None:
    """Walk right with the enemies off until Mario stands on the ground at world x >= `x`."""
    facts = env.facts
    walker = Walker()
    for _ in range(facts["walker"]["max_frames"]):
        if R.mario_x(env.ram, facts) >= x and int(env.ram[facts["ram"]["player_state"]]) == 0:
            return
        R.sweep_enemies(env, facts)
        if env.step(walker.act(env)).done:
            raise RuntimeError(f"walker died before x={x} at x={R.mario_x(env.ram, facts)}")
    raise RuntimeError(f"walker did not reach x={x} in {facts['walker']['max_frames']} frames")
