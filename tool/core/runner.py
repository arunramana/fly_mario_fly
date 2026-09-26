"""tool/core/runner.py -- RunSpec -> run_steering.main(...), the one path
both the Play button (P4) and a batch run (batch.py) go through
(tool/PLAN.md section 3).
"""

from __future__ import annotations

from pathlib import Path


def run_one(spec, on_frame=None, should_stop=None, arousal_source=None):
    """Runs one RunSpec synchronously in whatever process calls this -- a
    fresh one (a single Play), or a warm pool worker (batch.py). Routes
    through sim.project_runner.run_from_config so C1's config= plumbing
    (all 49 scalars, not just the scenario) is the only path a run ever
    takes, matching what a plain `python -m tool.core.cli run` and a
    parallel batch both actually execute.

    `RenderSettings.raw_frames` (default on): also records a cheap, no-
    brain-panel per-run frame recording (tool/core/frame_store.py) for the
    Run tab's video player, live-viewable and seekable from the same
    file. Lives HERE, not in run_one_streaming, so a batch run (which
    calls run_one directly, no streaming queue) gets one too --
    "batch runs appear as a group in the run drawer" needs their own
    recordings, the same as a single Play's.

    `RenderSettings.death_animation_frames` (default 90): on a real death
    or flag (not a Cancel, not hitting max_frames), run_steering.main()
    steps this many extra emulator frames purely for on_frame/the
    recording -- excluded from telemetry and fitness (run_steering.py's
    own docstring) -- so the player shows the NES's own death animation
    instead of cutting to the last standing frame.
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

    # A saved state (Goal tab "Start from") is replayed before frame 0 --
    # see tool/core/savestates.py. The brain starts fresh.
    start_state = None
    name = spec.tool_settings.experiment.start_state
    if name:
        from tool.core.savestates import load_state
        start_state = load_state(spec.project_name, name)
        if start_state["level"] != spec.config.scenario.level:
            raise ValueError(f"saved state {name!r} is for level {start_state['level']}, "
                             f"but this run is level {spec.config.scenario.level}")
    # RAM pokes cannot be replayed, so such runs record no action log.
    replayable = not (powerup_kwargs or spec.config.scenario.inject_gap_frame is not None)

    recorder = None
    raw_path = None
    if spec.tool_settings.render.raw_frames:
        from config.output_routing import resolve_run_path
        from tool.core.frame_store import FrameStore
        raw_path = resolve_run_path(spec.config, Path(spec.out_filename).stem + "_raw.npz")
        recorder = FrameStore()

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
        death_animation_frames=spec.tool_settings.render.death_animation_frames,
        start_actions=start_state["actions"] if start_state else None,
        arousal_source=arousal_source,
        record_actions=replayable,
        **powerup_kwargs,
    )
    actions = info.pop("actions", None)
    if actions is not None:
        import numpy as np
        from config.output_routing import resolve_run_path
        prefix = start_state["actions"] if start_state else np.empty(0, dtype=np.uint8)
        path = resolve_run_path(spec.config, Path(spec.out_filename).stem + "_actions.npy")
        path.parent.mkdir(parents=True, exist_ok=True)
        np.save(path, np.concatenate([prefix, actions]).astype(np.uint8))
        info["actions_path"] = str(path)
        info["actions_prefix_len"] = int(len(prefix))
    if start_state:
        info["start_state"] = {"name": start_state["name"], "frame": start_state["frame"],
                               "source_run": start_state["source_run"]}
    if recorder is not None:
        written = recorder.close(raw_path)
        info["raw_frames_path"] = str(written) if written else None
    return tel, info


def run_one_streaming(spec, frame_queue, stop_event, arousal_value=None):
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
            # .copy(): nes-py's own `obs` is ONE persistent buffer, mutated
            # in place by the C emulator core every step (NESEnv.screen is
            # assigned once and returned unchanged -- checked directly in
            # nes_py/nes_env.py) -- never a fresh array. multiprocessing.
            # Queue pickles asynchronously on its own feeder thread, so by
            # the time it gets to an entry queued here, the main thread may
            # already have overwritten -- or, once the episode ends and
            # env.close() runs, FREED -- that same buffer. Found live: this
            # raced hard enough to crash the feeder thread with a Windows
            # access violation while pickling (Python's own faulthandler
            # caught it mid-episode-cleanup) once a per-frame FrameStore
            # write gave the main thread enough extra work per frame to
            # change the timing -- almost certainly the real cause of the
            # unexplained multiprocessing hangs from the earlier ffmpeg-
            # recorder investigation too, not just this one.
            frame_queue.put_nowait(("frame", obs.copy(), row))
        except Exception:
            pass  # a full/closed queue drops frames rather than blocking the sim

    def should_stop():
        return stop_event.is_set()

    try:
        source = (lambda: arousal_value.value) if arousal_value is not None else None
        tel, info = run_one(spec, on_frame=on_frame, should_stop=should_stop, arousal_source=source)
        # Found in manual testing: a cancelled run was recorded and shown
        # exactly like a normal completed one, with nothing distinguishing
        # it from Cancel having done nothing at all. should_stop() being
        # True is definitive -- the loop only ever breaks on it, not on a
        # coincidental natural end at the same frame.
        info["cancelled"] = stop_event.is_set()
        frame_queue.put(("done", info))
    except Exception as exc:  # the parent process needs to know Play failed, not hang
        frame_queue.put(("error", str(exc)))
