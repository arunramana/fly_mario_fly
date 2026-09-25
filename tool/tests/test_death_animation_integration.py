"""End-to-end: a real death, through tool/core/runner.py's run_one() with
raw_frames + death_animation_frames both on (the shipped defaults), loaded
into the actual VideoPlayer. Each piece (frame_store.py, run_steering.py's
extension, the player's own longer-than-telemetry handling) has its own
unit tests; this is the one test proving they still fit together.
"""
from __future__ import annotations

import dataclasses
import shutil

from config.output_routing import PROJECTS_ROOT
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.runner import run_one

PROJECT_NAME = "_death_animation_integration_test"


def test_a_real_death_records_and_plays_back_its_own_animation(qapp):
    shutil.rmtree(PROJECTS_ROOT / PROJECT_NAME, ignore_errors=True)
    try:
        project = ToolProject.create(PROJECT_NAME)
        # Same scenario tests/test_golden.py's test_sigma0_baseline freezes:
        # 1-1, sigma=0, seed=0, dies at frame 689.
        project.config = dataclasses.replace(
            project.config, scenario=dataclasses.replace(project.config.scenario, max_frames=800))
        project.save()

        spec = RunSpec(project_name=PROJECT_NAME, config=project.config,
                        tool_settings=project.tool_settings, seed=0, out_filename="001_play_seed0.mp4")
        tel, info = run_one(spec)

        assert info["died_or_flagged"] is True
        assert info["raw_frames_path"] is not None
        real_frames = info["n_frames"]
        assert real_frames == len(tel)

        from tool.ui.widgets.video_player import VideoPlayer
        player = VideoPlayer()
        player.load_run(info["raw_frames_path"], tel, info)
        assert player._mode == "seekable"
        assert player._n_frames == real_frames + 90, "the recording should carry the death animation too"

        # Well past the real episode: the game view still has a real
        # recorded frame, and the Data drawer freezes on the last real row.
        player.seek_frame(real_frames + 50)
        assert not player.frame_label.pixmap().isNull()
        row = player.current_row()
        assert row is not None and row["frame"] == real_frames - 1
    finally:
        shutil.rmtree(PROJECTS_ROOT / PROJECT_NAME, ignore_errors=True)
