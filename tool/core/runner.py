"""tool/core/runner.py -- RunSpec -> run_steering.main(...), the one path
both the Play button (P4) and a batch run (batch.py) go through
(tool/PLAN.md section 3).
"""

from __future__ import annotations

from pathlib import Path


def run_one(spec, on_frame=None, should_stop=None):
    """Runs one RunSpec synchronously in whatever process calls this -- a
    fresh one (a single Play), or a warm pool worker (batch.py). Routes
    through sim.project_runner.run_from_config so C1's config= plumbing
    (all 49 scalars, not just the scenario) is the only path a run ever
    takes, matching what a plain `python -m tool.core.cli run` and a
    parallel batch both actually execute.

    `RenderSettings.raw_frames` (default on): also records a cheap, no-
    brain-panel raw-frame video (tool/core/raw_frame_recorder.py) for the
    Run tab's video player, live-viewable and seekable from the same
    file. Lives HERE, not in run_one_streaming, so a batch run (which
    calls run_one directly, no streaming queue) gets one too --
    "batch runs appear as a group in the run drawer" needs their own
    recordings, the same as a single Play's.
    """
    import setuptools  # noqa: F401 -- must precede gym, same rule as run_steering.py
    from sim.project_runner import run_from_config

    character = spec.tool_settings.character
    powerup_kwargs = {}
    if character.starting_powerup:
        powerup_kwargs = dict(force_mario_size=1, force_size_from_frame=0)

    entity_profiles = None
    if spec.tool_settings.entity_profile.enabled:
        from tool.core.entity_profiles_store import load_merged
        entity_profiles = load_merged(spec.project_name)

    recorder = None
    raw_path = None
    if spec.tool_settings.render.raw_frames:
        from config.output_routing import resolve_run_path
        from tool.core.raw_frame_recorder import RawFrameRecorder
        raw_path = resolve_run_path(spec.config, Path(spec.out_filename).stem + "_raw.mp4")
        recorder = RawFrameRecorder(raw_path)

    def combined_on_frame(frame, obs, row):
        recorder.write_frame(obs)
        if on_frame is not None:
            on_frame(frame, obs, row)

    tel, info = run_from_config(
        spec.config, spec.out_filename,
        seed=spec.seed,
        record_video=spec.tool_settings.render.record_video,
        frame_skip=spec.tool_settings.render.frame_skip,
        event_proximal_dopamine=spec.tool_settings.experiment.learning_enabled,
        shuffle_seed=spec.tool_settings.circuits.shuffle_seed,
        hunger_override=character.hunger_override,
        entity_profiles=entity_profiles,
        on_frame=combined_on_frame if recorder is not None else on_frame,
        should_stop=should_stop,
        **powerup_kwargs,
    )
    if recorder is not None:
        written = recorder.close()
        info["raw_frames_path"] = str(written) if written else None
    return tel, info


def run_one_streaming(spec, frame_queue, stop_event):
    """Runs one RunSpec, streaming ("frame", obs, row) tuples onto
    `frame_queue` and stopping early if `stop_event` is set -- meant to
    run in a child process the GUI spawns for Play (tool/PLAN.md P4).
    `obs`/`row` cross the process boundary through the queue exactly as
    `on_frame` received them (minus the unused `frame` positional -- the
    preview widget only ever reads `obs`, so it never crosses the process
    boundary); the parent process applies the Luigi colour swap
    (tool/core/palette.py) itself when it draws them, so this function
    stays display-agnostic.

    Throttled by `render.live_preview_fps` (tool/PLAN.md P7, tab 6's
    Settings control): the emulator runs at a fixed 60fps regardless, so
    a requested preview fps below that means sending every Nth frame,
    not skipping simulation steps. Frames are sent at full resolution
    (ease-of-use redesign) -- tool/ui/widgets/preview.py now scales up by
    a whole-number factor with nearest-neighbour sampling, so pixel art
    stays crisp; a pre-shrunk source frame would have thrown away the
    very pixels that scale-up needs.
    """
    fps = spec.tool_settings.render.live_preview_fps
    every_n = max(1, round(60 / max(1, fps)))
    counter = {"n": 0}

    def on_frame(frame, obs, row):
        counter["n"] += 1
        if counter["n"] % every_n != 0:
            return
        try:
            frame_queue.put_nowait(("frame", obs, row))
        except Exception:
            pass  # a full/closed queue drops frames rather than blocking the sim

    def should_stop():
        return stop_event.is_set()

    try:
        tel, info = run_one(spec, on_frame=on_frame, should_stop=should_stop)
        # Found in manual testing: a cancelled run was recorded and shown
        # exactly like a normal completed one, with nothing distinguishing
        # it from Cancel having done nothing at all. should_stop() being
        # True is definitive -- the loop only ever breaks on it, not on a
        # coincidental natural end at the same frame.
        info["cancelled"] = stop_event.is_set()
        frame_queue.put(("done", info))
    except Exception as exc:  # the parent process needs to know Play failed, not hang
        frame_queue.put(("error", str(exc)))
