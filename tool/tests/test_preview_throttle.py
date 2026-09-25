"""tool/PLAN.md P7: `render.live_preview_fps` must actually throttle what
`run_one_streaming` puts on the queue (ground rule 4, "no control lies") --
this is the test that promotes it from not_wired to live in
tool/core/wiring.py.
"""
from __future__ import annotations

import dataclasses
import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from config.project_config import ProjectConfig
from tool.core.run_spec import RunSpec
from tool.core.runner import run_one_streaming
from tool.core.tool_settings import RenderSettings, ToolSettings

PROJECT_NAME = "_preview_throttle_test"
MAX_FRAMES = 120


class _FakeQueue:
    def __init__(self):
        self.items = []

    def put_nowait(self, item):
        self.items.append(item)

    def put(self, item):
        self.items.append(item)

    def empty(self):
        return len(self.items) == 0

    def get_nowait(self):
        return self.items.pop(0)


class _FakeStopEvent:
    def is_set(self):
        return False


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _spec(fps, out_filename):
    cfg = ProjectConfig(
        scenario=dataclasses.replace(ProjectConfig().scenario, level="1-1", max_frames=MAX_FRAMES),
        output=dataclasses.replace(ProjectConfig().output, project_name=PROJECT_NAME),
    )
    settings = ToolSettings(render=dataclasses.replace(RenderSettings(), live_preview_fps=fps))
    return RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=settings,
                    seed=0, out_filename=out_filename)


def test_lower_fps_sends_fewer_frames(clean_project):
    queue_60 = _FakeQueue()
    run_one_streaming(_spec(60, "fast.mp4"), queue_60, _FakeStopEvent())
    frames_60 = [m for m in queue_60.items if m[0] == "frame"]
    n_frames = [m for m in queue_60.items if m[0] == "done"][0][1]["n_frames"]

    queue_15 = _FakeQueue()
    run_one_streaming(_spec(15, "slow.mp4"), queue_15, _FakeStopEvent())
    frames_15 = [m for m in queue_15.items if m[0] == "frame"]

    # 60fps -> every_n=1 (every frame), 15fps -> every_n=4 (every 4th frame).
    assert len(frames_60) == n_frames
    assert len(frames_15) == pytest.approx(n_frames / 4, abs=2)
    assert len(frames_15) < len(frames_60)


def test_sent_frames_are_full_resolution(clean_project):
    """Ease-of-use redesign: frames used to be strided 2x before crossing
    the process boundary; now they cross at full resolution and
    tool/ui/widgets/preview.py scales up by a whole-number factor with
    nearest-neighbour sampling instead."""
    queue = _FakeQueue()
    run_one_streaming(_spec(60, "full_res.mp4"), queue, _FakeStopEvent())
    obs, _row = next((m[1], m[2]) for m in queue.items if m[0] == "frame")
    # NES frame is 240x256 (tool/ui/widgets/preview.py's own minimum size).
    assert obs.shape[:2] == (240, 256)
