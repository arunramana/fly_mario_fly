"""The runner: joins Mario to the fly, one frame at a time. Everything outside this package (evolve, api, render)
goes through here and never names a particular object or sense.

    from fly_mario.runner import load_fly, Run, Scene
    run = Run(load_fly("champion_e1s"), Scene("1-1", noop=3, sigma=0.05, seed=101))
    result = run.play()
"""
from fly_mario.contracts import FlyConfig, RunRequest, RunResult, SavedMoment, Scene
from fly_mario.runner.config import (active_actions, active_senses, brain_spec, dump_fly, fly_from_dict, fly_to_dict,
                                     knob_specs, load_fly, resolve_knobs, validate)
from fly_mario.runner.display import BrainDisplay, GroupDisplay, all_somata, brain_display, terminal_positions
from fly_mario.runner.levels import LevelInfo, LevelStatus, level_catalogue, level_info, level_objects, level_statuses, precompute, scan_level
from fly_mario.runner.moments import (MomentInfo, Try, delete_moment, describe_change, get_moment, list_moments,
                                     moment_info, rename_moment, save_moment, tries_from)
from fly_mario.runner.record import new_run_id, save_run
from fly_mario.runner.session import FrameRecord, Options, Run, get_brain, resolve_buttons, screen_scroll

__all__ = ["FlyConfig", "RunRequest", "RunResult", "SavedMoment", "Scene", "Run", "Options", "FrameRecord",
           "load_fly", "dump_fly", "fly_from_dict", "fly_to_dict", "validate", "resolve_knobs", "knob_specs",
           "active_senses", "active_actions", "brain_spec", "get_brain", "resolve_buttons", "new_run_id", "save_run",
           "screen_scroll", "LevelInfo", "LevelStatus", "level_catalogue", "level_statuses", "scan_level", "level_info", "level_objects", "precompute",
           "MomentInfo", "Try", "save_moment", "get_moment", "moment_info", "list_moments", "rename_moment",
           "delete_moment", "tries_from", "describe_change", "BrainDisplay", "GroupDisplay", "brain_display", "all_somata", "terminal_positions"]
