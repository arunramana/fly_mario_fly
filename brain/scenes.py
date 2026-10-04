# What this file does, in plain English:
# Builds the test scene for experiment E1 ("jump the Goomba"). The scene is a
# fixed list of button presses, stored in the repo, that takes Mario from the
# start of level 1-1 to a spot where he stands still and the first Goomba is on
# screen walking toward him. The game is deterministic, so replaying the list
# always gives the same scene. The fly takes over on the frame after the list;
# nothing in this file decides anything for the fly.
"""brain/scenes.py -- docs/SPEC_tool_phase2.md section 2.

A scene is `brain/scenes/<id>.json` (manifest) replayed from reset by `build_scene`. `check_scene` verifies only that
the scene is what the manifest says: a Goomba on screen ahead of a living, stationary Mario. It never looks at how the
fly does in it, and the log is not edited against results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mario.actions.actions import action_from_buttons
from mario.entities.registry import GOOMBA_TYPE_BYTE
from mario.ram import screen
from mario.ram.addresses import (ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE,
                                 ADDR_MARIO_X, ADDR_MARIO_XSPEED, N_ENEMY_SLOTS)

SCENES_DIR = Path(__file__).resolve().parent / "scenes"
E1_SCENE_ID = "e1_goomba_approach"


@dataclass(frozen=True)
class SceneSpec:
    id: str
    experiment: str
    level: str
    description: str
    log: tuple[tuple[tuple[str, ...], int], ...]     # (buttons, frames) segments, in order
    raw: str                                          # the manifest text (hashed into the run stamp)

    @property
    def n_frames(self) -> int:
        return sum(n for _, n in self.log)

    def actions(self) -> np.ndarray:
        """The explicit per-frame action log (uint8 indices into mario.actions.MOVES_ALL)."""
        out = []
        for buttons, n in self.log:
            held = {b.lower() for b in buttons}
            idx = action_from_buttons(right="right" in held, left="left" in held, down="down" in held,
                                      up="up" in held, a="a" in held, b="b" in held)
            out += [idx] * n
        return np.asarray(out, dtype=np.uint8)

    def hash(self) -> str:
        return hashlib.sha256(self.raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {"id": self.id, "level": self.level, "log_frames": self.n_frames, "scene_hash": self.hash()}


def load_scene(scene_id: str = E1_SCENE_ID) -> SceneSpec:
    raw = (SCENES_DIR / f"{scene_id}.json").read_text(encoding="utf-8")
    d = json.loads(raw)
    return SceneSpec(d["id"], d["experiment"], d["level"], d["description"],
                     tuple((tuple(s["buttons"]), int(s["frames"])) for s in d["action_log"]), raw)


def build_scene(env, spec: SceneSpec) -> None:
    """Reset `env` and replay the scene's log; the env is left on the takeover frame."""
    env.reset()
    for a in spec.actions():
        _, _, done, _ = env.step(int(a))
        if done:
            raise RuntimeError(f"scene {spec.id}: the action log ended the episode")


def goomba_slots(ram) -> list[int]:
    return [s for s in range(N_ENEMY_SLOTS)
            if ram[ADDR_ENEMY_ACTIVE + s] and ram[ADDR_ENEMY_TYPE + s] == GOOMBA_TYPE_BYTE]


def check_scene(ram) -> dict:
    """What the manifest promises, nothing about the fly: one Goomba on screen and ahead of Mario, Mario standing still."""
    slots = [s for s in goomba_slots(ram) if screen.enemy_on_screen(ram, s, 16)]
    mario_world = int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X])
    dx = [int(ram[ADDR_ENEMY_PAGE + s]) * 256 + int(ram[ADDR_ENEMY_X + s]) - mario_world for s in slots]
    return {"goomba_on_screen": bool(slots), "goomba_ahead": bool(dx) and dx[0] > 0, "goomba_dx_px": dx[0] if dx else None,
            "mario_stationary": int(ram[ADDR_MARIO_XSPEED]) == 0}
