"""tool/core/runner.py's run_one_streaming: obs.copy() before queuing.

Found live: nes-py's own `obs` is ONE persistent buffer, mutated in place
by the C emulator core every step (NESEnv.screen assigned once, returned
unchanged on every step/reset -- checked directly in nes_py/nes_env.py),
never a fresh array per frame. multiprocessing.Queue pickles asynchronously
on its own feeder thread; queuing that buffer by reference let the main
thread overwrite -- or, once the episode ends, free -- it before the
feeder thread got to pickle it, which crashed the feeder thread with a
Windows access violation once a per-frame FrameStore write (tool/core/
frame_store.py) gave the main thread enough extra work per frame to
change the timing. Reproduced with a real MainWindow + a real spawned
Play; this test exercises the actual bug in-process, no multiprocessing
or GUI needed -- a fake frame_queue plus a fake run_from_config that
mutates ONE shared buffer between on_frame calls, exactly like nes-py
does.
"""
from __future__ import annotations

import numpy as np

import tool.core.runner as runner_module
from tool.core.run_spec import RunSpec
from tool.core.tool_settings import ToolSettings


class _FakeQueue:
    def __init__(self):
        self.items = []

    def put_nowait(self, item):
        self.items.append(item)

    def put(self, item):
        self.items.append(item)


def test_queued_frames_are_independent_of_the_shared_mutable_buffer(monkeypatch):
    shared_buffer = np.zeros((4, 4, 3), dtype=np.uint8)

    def fake_run_from_config(config, out_filename, **kwargs):
        on_frame = kwargs["on_frame"]
        for i in range(3):
            shared_buffer[:] = i  # nes-py's own in-place mutation, same object every call
            on_frame(i, shared_buffer, {"frame": i})
        shared_buffer[:] = 99  # simulates the buffer still changing after the last queued frame
        return None, {"n_frames": 3, "died_or_flagged": False}

    monkeypatch.setattr(runner_module, "run_from_config", fake_run_from_config, raising=False)
    monkeypatch.setattr("sim.project_runner.run_from_config", fake_run_from_config)

    import dataclasses
    from config.project_config import ProjectConfig
    # raw_frames=False: this test is about the queue-aliasing bug in
    # on_frame itself, independent of whether FrameStore is also active.
    settings = dataclasses.replace(ToolSettings(), render=dataclasses.replace(
        ToolSettings().render, raw_frames=False, live_preview_fps=60))  # no throttling -- every frame queued
    spec = RunSpec(project_name="_unused", config=ProjectConfig(),
                    tool_settings=settings, seed=0, out_filename="run.mp4")

    queue = _FakeQueue()
    stop_event = type("E", (), {"is_set": lambda self: False})()
    runner_module.run_one_streaming(spec, queue, stop_event)

    frame_msgs = [m for m in queue.items if m[0] == "frame"]
    assert len(frame_msgs) == 3
    for i, (_kind, obs, _row) in enumerate(frame_msgs):
        assert obs is not shared_buffer, "queuing the buffer itself is exactly the bug"
        assert (obs == i).all(), f"frame {i} should still show its own value, not a later mutation"
