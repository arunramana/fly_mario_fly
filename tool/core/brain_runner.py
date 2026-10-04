# What this file does, in plain English:
# The tool's way of running the redesigned brain, alongside (not instead of)
# the old runner. It plays one E1 episode with the fly in control, saves what
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

BRAIN_RUN_KIND = "brain_e1"
PREVIEW_EVERY_N = 2          # live preview: every 2nd frame (the brain runs well above real time, the queue need not carry all)


def brain_run_slug(number: int, arm: str, seed: int) -> str:
    return f"{number:03d}_e1_{arm}_seed{seed}"


def run_brain_one(project_name: str, slug: str, seed: int, shuffle_seed: int | None, on_frame=None, should_stop=None):
    """Play one E1 episode and write its recording. Returns (telemetry DataFrame, info dict, run_spec dict)."""
    import pandas as pd
    from brain.e1 import run_e1_episode
    from brain.scenes import load_scene
    from tool.core.frame_store import FrameStore
    scene = load_scene()
    recorder = FrameStore()

    def combined(frame, obs, row):
        recorder.write_frame(obs, (row.get("mario_sx"), row.get("mario_y")))
        if on_frame is not None:
            on_frame(frame, obs, row)

    result, rows, stamp = run_e1_episode(seed, shuffle_seed, scene=scene, on_frame=combined, should_stop=should_stop,
                                         record_rows=True)
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
            "kind": BRAIN_RUN_KIND, "experiment": "E1", "arm": result.arm,
            "raw_frames_path": str(raw) if raw else None, "actions_path": str(actions_path),
            "actions_prefix_len": int(len(prefix)), "e1": result.__dict__.copy(), "build_hash": stamp["build_hash"]}
    spec = {"kind": BRAIN_RUN_KIND, "experiment": "E1", "seed": seed, "shuffle_seed": shuffle_seed,
            "scene": stamp["scene"], "stamp": _jsonable(stamp)}
    return tel, info, spec


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=str))


def run_brain_streaming(project_name: str, slug: str, seed: int, shuffle_seed: int | None, queue, stop_event) -> None:
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
        _tel, info, spec = run_brain_one(project_name, slug, seed, shuffle_seed, on_frame, stop_event.is_set)
        info["cancelled"] = stop_event.is_set()
        queue.put(("done", info, spec))
    except Exception as exc:  # the parent must learn it failed, not hang
        import traceback
        queue.put(("error", f"{exc}\n{traceback.format_exc()}"))


def _auto_lesson(e: dict) -> str:
    """One auto-filled sentence from the recorded numbers (restates them, no interpretation)."""
    gf = ("the Giant Fiber never fired" if not e["gf_fired"] else
          f"the Giant Fiber fired at frame {e['first_gf_frame']}" +
          (", before contact" if e["gf_before_contact"] else ", after contact"))
    a = f"A was held {e['a_frames']} frames" if e["a_pressed"] else "A was never pressed"
    return (f"Auto-filled from the run's numbers: {e['arm']} arm, {gf}, {a}; outcome {e['outcome']} "
            f"({'survived' if e['survived'] else 'did not survive'}). One seed is an observation, not a result.")


def write_brain_run_note(project_name: str, number: int, slug: str, seed: int, info: dict) -> Path:
    e = info["e1"]
    path = PROJECTS_ROOT / project_name / "runs" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {number:03d} -- {slug}\n\n"
        f"**Setup.** E1 jump the Goomba, {e['arm']} connectome, brain noise seed {seed}, shuffle seed {e['shuffle_seed']}, "
        f"network {info.get('build_hash')}.\n\n"
        f"**What happened.** {e['frames']} frames, outcome {e['outcome']}, survived {e['survived']}, "
        f"GF before contact {e['gf_before_contact']} (theta {e['theta_at_gf_deg']}, distance {e['distance_at_gf_px']}), "
        f"A pressed {e['a_pressed']}.\n\n**What we learned.** {_auto_lesson(e)}\n", encoding="utf-8")
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


def run_brain_eval_streaming(project_name: str, queue, workers: int = 4, n: int | None = None, seed0: int | None = None) -> None:
    """Child-process entry for the Results screen's Run E1 eval button (non-daemon: it starts its own pool)."""
    try:
        from brain import e1
        result = e1.run_eval(e1.E1_N if n is None else n, e1.E1_SEED0 if seed0 is None else seed0, workers)
        save_brain_eval(project_name, result)
        queue.put(("done", result))
    except Exception as exc:
        import traceback
        queue.put(("error", f"{exc}\n{traceback.format_exc()}"))


def format_brain_eval(result: dict) -> str:
    from brain.e1 import format_eval
    return format_eval(result)
