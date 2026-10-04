# What this file does, in plain English:
# The tool's way of running the redesigned brain, alongside (not instead of)
# the old runner. It plays one E0, E1 or E3 episode with the fly in control, saves what
# the Watch screen needs (the frames, a per-frame log of the brain's outputs,
# the button presses) and a summary, and it runs the 20-seed real-vs-shuffled
# evaluation for the Results screen. It never changes the brain; the old
# tool/core/runner.py is untouched.
"""tool/core/brain_runner.py -- docs/SPEC_tool_phase2.md section 6.

A brain run is recorded in the project's run index like any other run (so the Run tab, i.e. Watch, plays it), with
`run_spec = {"kind": "brain_e1", ...}` holding what reproduces it: experiment, scene hash, seed, shuffle seed and the
brain stamp. Evaluations are appended to `projects/<name>/brain_eval.json` for the Results screen.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from config.output_routing import PROJECTS_ROOT

BRAIN_RUN_KIND = "brain_e1"          # E1 runs; E0 and E3 runs are "brain_e0" / "brain_e3" (run_kind)
RUNNABLE = ("E0", "E1", "E3", "B11")
SETTINGS_FILE = "brain_settings.json"   # the Mechanisms tab's per-object pursuit setting and home-landmark strength
PREVIEW_EVERY_N = 2          # live preview: every 2nd frame (the brain runs well above real time, the queue need not carry all)


def run_kind(experiment: str) -> str:
    return BRAIN_RUN_KIND if experiment == "E1" else f"brain_{experiment.lower()}"


def brain_run_slug(number: int, arm: str, seed: int, experiment: str = "E1") -> str:
    return f"{number:03d}_{experiment.lower()}_{arm}_seed{seed}"


# ---- the Mechanisms tab's settings (per project) ---------------------------------------------------------------------------
def load_sense_settings(project_name: str):
    """The user's sense settings for this project (docs/SPEC_phase3.md): defaults until the Mechanisms tab saves some."""
    from brain.settings import SenseSettings
    p = PROJECTS_ROOT / project_name / SETTINGS_FILE
    return SenseSettings.from_dict(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else SenseSettings.user_default()


def save_sense_settings(project_name: str, settings) -> None:
    p = PROJECTS_ROOT / project_name / SETTINGS_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(settings.to_dict(), indent=1), encoding="utf-8")


def run_brain_one(project_name: str, slug: str, seed: int, shuffle_seed: int | None, on_frame=None, should_stop=None,
                  experiment: str = "E1", settings: dict | None = None, shuffle_mode: str = "shuffled"):
    """Play one E0, E1 or E3 episode and write its recording. Returns (telemetry DataFrame, info dict, run_spec dict).
    `settings` is the user's sense settings (a dict); the experiment's own mechanism list decides which apply."""
    import pandas as pd
    from brain.e1 import run_e1_episode
    from brain.goal_eval import SCENES, run_goal_episode
    from brain.baseline import run_baseline_episode
    from brain.scenes import B11_SCENE_ID, load_scene
    from brain.settings import SenseSettings
    from tool.core.frame_store import FrameStore
    scene = load_scene({**SCENES, "B11": B11_SCENE_ID}[experiment]) if experiment != "E1" else load_scene()
    recorder = FrameStore()

    def combined(frame, obs, row):
        recorder.write_frame(obs, (row.get("mario_sx"), row.get("mario_y")))
        if on_frame is not None:
            on_frame(frame, obs, row)

    if experiment == "E1":
        result, rows, stamp = run_e1_episode(seed, shuffle_seed, scene=scene, on_frame=combined, should_stop=should_stop,
                                             record_rows=True)
    elif experiment == "B11":
        arm = "real" if shuffle_seed is None else shuffle_mode
        result, rows, stamp = run_baseline_episode(seed, arm, shuffle_seed, (SenseSettings.from_dict(settings) if settings is not None else SenseSettings.user_default()),
                                                   scene=scene, on_frame=combined, should_stop=should_stop, record_rows=True)
    else:
        arm = "real" if shuffle_seed is None else shuffle_mode
        result, rows, stamp = run_goal_episode(experiment, seed, arm, shuffle_seed, (SenseSettings.from_dict(settings) if settings is not None else SenseSettings.user_default()),
                                               scene=scene, on_frame=combined, should_stop=should_stop, record_rows=True)
    root = PROJECTS_ROOT / project_name
    (root / "telemetry").mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    tel = pd.DataFrame(rows)
    tel.to_csv(root / "telemetry" / f"{slug}_telemetry.csv", index=False)
    raw = recorder.close(root / "runs" / f"{slug}_raw.npz")
    prefix = scene.actions()
    actions_path = root / "runs" / f"{slug}_actions.npy"
    np.save(actions_path, np.concatenate([prefix, tel["action"].to_numpy(dtype=np.uint8)]).astype(np.uint8))
    info = {"n_frames": result.frames, "died_or_flagged": result.died, "max_x_abs": result.max_x, "score": 0,
            "kind": run_kind(experiment), "experiment": experiment, "arm": result.arm,
            "raw_frames_path": str(raw) if raw else None, "actions_path": str(actions_path),
            "actions_prefix_len": int(len(prefix)), "e1" if experiment == "E1" else "episode": result.__dict__.copy(),
            "build_hash": stamp["build_hash"]}
    spec = {"kind": run_kind(experiment), "experiment": experiment, "seed": seed, "shuffle_seed": shuffle_seed,
            "scene": stamp["scene"], "stamp": _jsonable(stamp)}
    return tel, info, spec


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=str))


def run_brain_streaming(project_name: str, slug: str, seed: int, shuffle_seed: int | None, queue, stop_event,
                        experiment: str = "E1", settings: dict | None = None, shuffle_mode: str = "shuffled") -> None:
    """Child-process entry for the Experiments screen's Run button: streams ("frame", obs, row), then ("done", info, spec)
    or ("error", text)."""
    counter = {"n": 0}

    def on_frame(frame, obs, row):
        counter["n"] += 1
        if counter["n"] % PREVIEW_EVERY_N == 0:
            try:
                queue.put_nowait(("frame", obs.copy(), row))    # .copy(): nes-py reuses one buffer
            except Exception:
                pass

    try:
        _tel, info, spec = run_brain_one(project_name, slug, seed, shuffle_seed, on_frame, stop_event.is_set,
                                         experiment, settings, shuffle_mode)
        info["cancelled"] = stop_event.is_set()
        queue.put(("done", info, spec))
    except Exception as exc:  # the parent must learn it failed, not hang
        import traceback
        queue.put(("error", f"{exc}\n{traceback.format_exc()}"))


def episode_of(info: dict) -> dict:
    """The recorded episode result: `e1` for E1 runs, `episode` for E0 and E3."""
    return info["e1"] if "e1" in info else info["episode"]


def _auto_lesson(e: dict) -> str:
    """One auto-filled sentence from the recorded numbers (restates them, no interpretation)."""
    if "reached" in e:                         # E0 / E3
        gf = ("the Giant Fiber never crossed threshold" if not e["gf_fired"]
              else f"the Giant Fiber crossed threshold at frame {e['first_gf_frame']}")
        at = "" if e["reached_frame"] is None else f" at frame {e['reached_frame']}"
        return (f"Auto-filled from the run's numbers: {e['experiment']}, {e['arm']} arm, outcome {e['outcome']} "
                f"({'reached' if e['reached'] else 'did not reach'} the target{at}); {gf}; Left pressed {e['left_frames']} "
                f"frames, Right {e['right_frames']}, walk (B) {e['b_frames']}; GF output max {e['gf_output_max_hz']:.2f} Hz, TTMn max "
                f"{e['ttmn_max_hz']:.3f} Hz. One seed is an observation, not a result.")
    gf = ("the Giant Fiber never fired" if not e["gf_fired"] else
          f"the Giant Fiber fired at frame {e['first_gf_frame']}" +
          (", before contact" if e["gf_before_contact"] else ", after contact"))
    a = f"A was held {e['a_frames']} frames" if e["a_pressed"] else "A was never pressed"
    return (f"Auto-filled from the run's numbers: {e['arm']} arm, {gf}, {a}; outcome {e['outcome']} "
            f"({'survived' if e['survived'] else 'did not survive'}). One seed is an observation, not a result.")


def write_brain_run_note(project_name: str, number: int, slug: str, seed: int, info: dict) -> Path:
    e = episode_of(info)
    exp = info.get("experiment", "E1")
    path = PROJECTS_ROOT / project_name / "runs" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if exp == "E1":
        what = (f"{e['frames']} frames, outcome {e['outcome']}, survived {e['survived']}, "
                f"GF before contact {e['gf_before_contact']} (theta {e['theta_at_gf_deg']}, distance {e['distance_at_gf_px']}), "
                f"A pressed {e['a_pressed']}.")
        title = "E1 jump the Goomba"
    else:
        what = (f"{e['frames']} frames, outcome {e['outcome']}, reached {e['reached']}, max x {e['max_x']}, GF fired {e['gf_fired']}, "
                f"GF output max {e['gf_output_max_hz']:.2f} Hz, TTMn max {e['ttmn_max_hz']:.3f} Hz, A pressed {e['a_pressed']}.")
        title = {"E0": "E0 walk to the goal", "E3": "E3 pursue the mushroom by sight", "B11": "B11 1-1 innate baseline"}[exp]
    path.write_text(
        f"# {number:03d} -- {slug}\n\n"
        f"**Setup.** {title}, {e['arm']} connectome, brain noise seed {seed}, shuffle seed {e['shuffle_seed']}, "
        f"network {info.get('build_hash')}.\n\n"
        f"**What happened.** {what}\n\n**What we learned.** {_auto_lesson(e)}\n", encoding="utf-8")
    return path


# ---- evaluation store (Results screen) ---------------------------------------------------------------------------------
def brain_eval_path(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / "brain_eval.json"


def load_brain_evals(project_name: str) -> list[dict]:
    p = brain_eval_path(project_name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save_brain_eval(project_name: str, result: dict) -> None:
    """Append one E1 evaluation (per-episode rows included) with a timestamp."""
    p = brain_eval_path(project_name)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {**result, "time": datetime.now(timezone.utc).isoformat()}
    p.write_text(json.dumps(load_brain_evals(project_name) + [_jsonable(entry)], indent=1), encoding="utf-8")


def run_brain_eval_streaming(project_name: str, queue, workers: int = 4, n: int | None = None, seed0: int | None = None,
                             experiment: str = "E1", settings: dict | None = None) -> None:
    """Child-process entry for the Results screen's evaluation button (non-daemon: it starts its own pool)."""
    try:
        if experiment == "E1":
            from brain import e1
            result = e1.run_eval(e1.E1_N if n is None else n, e1.E1_SEED0 if seed0 is None else seed0, workers)
        elif experiment == "B11":
            from brain import baseline
            from brain.settings import SenseSettings
            result = baseline.run_eval(baseline.N if n is None else n, seed0, workers,
                                       settings=SenseSettings.from_dict(settings) if settings is not None else None)
        else:
            from brain import goal_eval
            from brain.settings import SenseSettings
            result = goal_eval.run_eval(experiment, goal_eval.N if n is None else n, seed0, workers,
                                        settings=SenseSettings.from_dict(settings) if settings is not None else None)
        save_brain_eval(project_name, result)
        queue.put(("done", result))
    except Exception as exc:
        import traceback
        queue.put(("error", f"{exc}\n{traceback.format_exc()}"))


def format_brain_eval(result: dict) -> str:
    if result.get("experiment", "E1") == "B11":
        from brain.baseline import format_eval as format_baseline
        return format_baseline(result)
    if result.get("experiment", "E1") != "E1":
        from brain.goal_eval import format_eval as format_goal
        return format_goal(result)
    from brain.e1 import format_eval
    return format_eval(result)
