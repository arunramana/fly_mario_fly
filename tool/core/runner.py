"""tool/core/runner.py -- RunSpec -> run_steering.main(...), the one path
both the Play button (P4) and a batch run (batch.py) go through
(tool/PLAN.md section 3).
"""

from __future__ import annotations


def run_one(spec, on_frame=None, should_stop=None):
    """Runs one RunSpec synchronously in whatever process calls this -- a
    fresh one (a single Play), or a warm pool worker (batch.py). Routes
    through sim.project_runner.run_from_config so C1's config= plumbing
    (all 49 scalars, not just the scenario) is the only path a run ever
    takes, matching what a plain `python -m tool.core.cli run` and a
    parallel batch both actually execute.
    """
    import setuptools  # noqa: F401 -- must precede gym, same rule as run_steering.py
    from sim.project_runner import run_from_config

    character = spec.tool_settings.character
    powerup_kwargs = {}
    if character.starting_powerup:
        powerup_kwargs = dict(force_mario_size=1, force_size_from_frame=0)

    tel, info = run_from_config(
        spec.config, spec.out_filename,
        seed=spec.seed,
        record_video=spec.tool_settings.render.record_video,
        frame_skip=spec.tool_settings.render.frame_skip,
        event_proximal_dopamine=spec.tool_settings.experiment.learning_enabled,
        shuffle_seed=spec.tool_settings.circuits.shuffle_seed,
        hunger_override=character.hunger_override,
        on_frame=on_frame,
        should_stop=should_stop,
        **powerup_kwargs,
    )
    return tel, info


def run_one_streaming(spec, frame_queue, stop_event):
    """Runs one RunSpec, streaming (frame, obs, row) tuples onto
    `frame_queue` and stopping early if `stop_event` is set -- meant to
    run in a child process the GUI spawns for Play (tool/PLAN.md P4).
    `obs`/`row` cross the process boundary through the queue exactly as
    `on_frame` received them; the parent process applies the Luigi
    colour swap (tool/core/palette.py) itself when it draws them, so this
    function stays display-agnostic.
    """
    def on_frame(frame, obs, row):
        try:
            frame_queue.put_nowait(("frame", frame, obs, row))
        except Exception:
            pass  # a full/closed queue drops frames rather than blocking the sim

    def should_stop():
        return stop_event.is_set()

    try:
        tel, info = run_one(spec, on_frame=on_frame, should_stop=should_stop)
        frame_queue.put(("done", info))
    except Exception as exc:  # the parent process needs to know Play failed, not hang
        frame_queue.put(("error", str(exc)))
