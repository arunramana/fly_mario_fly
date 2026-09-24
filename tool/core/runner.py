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

    tel, info = run_from_config(
        spec.config, spec.out_filename,
        seed=spec.seed,
        record_video=spec.tool_settings.render.record_video,
        frame_skip=spec.tool_settings.render.frame_skip,
        event_proximal_dopamine=spec.tool_settings.experiment.learning_enabled,
        on_frame=on_frame,
        should_stop=should_stop,
    )
    return tel, info
