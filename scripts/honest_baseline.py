# What this file does, in plain English:
# Runs the read-only "honest" project once on level 1-1 (video included),
# records it in the project's run list, replays the button presses to find out
# how Mario died, prints which stimuli and neurons were active in the last 60
# frames, and saves a save-state 60 frames before the death.
"""scripts/honest_baseline.py -- the honest project's baseline (docs/RUNS.md).

    .venv/Scripts/python.exe -m scripts.honest_baseline [--seed 0]
"""

from __future__ import annotations

import argparse
import dataclasses
import json

import numpy as np
import pandas as pd

from config.output_routing import PROJECTS_ROOT
from mario.ram import tile_ram
from mario.ram.addresses import (
    ADDR_ENEMY_ACTIVE, ADDR_ENEMY_PAGE, ADDR_ENEMY_TYPE, ADDR_ENEMY_X, ADDR_MARIO_PAGE, ADDR_MARIO_X,
    ADDR_MARIO_Y, N_ENEMY_SLOTS, POWERUP_ID)
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.run_store import next_run_number, record_run, list_runs, write_run_note
from tool.core.runner import run_one
from tool.core.savestates import capture_from_run

PROJECT = "honest"
LAST_N = 60
# Stimulus / neuron columns worth reading in the last frames, grouped.
STIMULI = ["theta", "dtheta", "d_px", "gap", "wall_tiles", "wall_height", "wall_theta", "wall_dtheta",
           "wall_takeoff", "odor_r", "avers_l", "avers_r", "refusing"]
NEURONS = ["lc4_r", "lc4_l", "lplc2_r", "lplc2_l", "ttmn", "ttmn_dnp02", "dlmn", "dnp09", "dna01", "dna02",
           "r_team", "l_team", "mdn", "motor_drive"]
EVENTS = ["spike", "spike_dnp02", "press_a", "press_b", "long_jump", "climb", "mdn_backing_up"]


def replay_death(actions, level: str) -> dict:
    """Replay the action log and read what killed Mario from the emulator's own RAM."""
    import setuptools  # noqa: F401 -- before gym
    from mario.emulator.env import make_env
    env = make_env(level)
    env.reset()
    ram = env.unwrapped.ram
    trail = []
    info = {}
    for a in actions:
        trail.append(dict(x=int(ram[ADDR_MARIO_PAGE]) * 256 + int(ram[ADDR_MARIO_X]), y=int(ram[ADDR_MARIO_Y]),
                          viewport=int(ram[0x00B5]), state=int(ram[0x001D]), ram=np.array(ram).copy()))
        _obs, _r, done, info = env.step(int(a))
        if done:
            break
    env.close()
    last = trail[-1]
    r = last["ram"]
    mario_abs = last["x"]
    enemies = []
    for i in range(N_ENEMY_SLOTS):
        if r[ADDR_ENEMY_ACTIVE + i] and r[ADDR_ENEMY_TYPE + i] != POWERUP_ID:
            ex = int(r[ADDR_ENEMY_PAGE + i]) * 256 + int(r[ADDR_ENEMY_X + i])
            enemies.append(dict(slot=i, type=hex(int(r[ADDR_ENEMY_TYPE + i])), dx=ex - mario_abs))
    nearest = min(enemies, key=lambda e: abs(e["dx"]), default=None)
    fell = last["viewport"] > 1 or last["y"] > 0xB0
    contact = nearest is not None and abs(nearest["dx"]) <= 20
    obstacle = tile_ram.obstacle_ahead(r, 6)
    pit = tile_ram.distance_to_gap(r, 8)
    cause = ("fell into a pit" if fell and not contact else
             "enemy contact" if contact else "fell into a pit" if fell else "unknown (time up or other)")
    return dict(cause=cause, x=mario_abs, y=last["y"], viewport=last["viewport"],
                nearest_enemy=nearest, enemies=enemies, obstacle_ahead=obstacle, pit_distance_tiles=pit,
                flag_get=bool(info.get("flag_get")), life=info.get("life"), time_left=info.get("time"))


def summarise(tel: pd.DataFrame, cols) -> dict:
    tail = tel.tail(LAST_N)
    out = {}
    for c in cols:
        if c not in tail:
            continue
        v = pd.to_numeric(tail[c], errors="coerce")
        if v.notna().any():
            out[c] = dict(max=round(float(v.max()), 3), mean=round(float(v.mean()), 3),
                          last=round(float(v.iloc[-1]), 3),
                          active=int((v.fillna(0).abs() > 1e-9).sum()))
    return out


def main(seed: int = 0) -> None:
    project = ToolProject.open(PROJECT)
    number = next_run_number(PROJECT)
    slug = f"{number:03d}_baseline_1-1"
    tool_settings = dataclasses.replace(
        project.tool_settings, render=dataclasses.replace(project.tool_settings.render, record_video=True))
    spec = RunSpec(project_name=PROJECT, config=project.config, tool_settings=tool_settings, seed=seed,
                   out_filename=f"{slug}.mp4")
    tel, info = run_one(spec)
    record_run(PROJECT, number, slug, seed, info, spec.to_dict())
    write_run_note(PROJECT, number, slug, seed, project.config, tool_settings, info)

    death = replay_death(np.load(info["actions_path"]), project.config.scenario.level)
    n = int(info["n_frames"])
    entry = next(e for e in list_runs(PROJECT) if e["number"] == number)
    state = capture_from_run(PROJECT, entry, max(0, n - LAST_N), name=f"{slug}_pre_death")
    report = dict(run=number, n_frames=n, max_x_abs=info["max_x_abs"], died_or_flagged=info["died_or_flagged"],
                  death=death, savestate=state,
                  stimuli_last60=summarise(tel, STIMULI), neurons_last60=summarise(tel, NEURONS),
                  events_last60=summarise(tel, EVENTS),
                  counts={k: info[k] for k in ("n_escape_jumps", "n_long_jumps", "n_dnp01_fired", "n_dnp02_fired",
                                               "n_climb_hops", "n_climb_jumps", "n_stomps", "n_refusals")})
    out = PROJECTS_ROOT / PROJECT / "runs" / f"{slug}_report.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    main(p.parse_args().seed)
