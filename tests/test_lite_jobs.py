"""The queue: one run per key, a bounded line, a rate limit per client, and failures that are reported and never cached."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from lite_support import FakeEngine, config, request

from fly_mario_fly.lite.cache import DiskCache
from fly_mario_fly.lite.jobs import Jobs, QueueFull, RateLimited
from fly_mario_fly.lite.settings import canonicalize


def make(tmp_path, engine, **kw):
    cfg = config(tmp_path, **kw)
    cache = DiskCache(cfg.cache_dir, cfg.cache_max_bytes)
    pool = ThreadPoolExecutor(max_workers=cfg.workers)
    return cfg, cache, Jobs(cfg, cache, pool, engine), pool


def st(cfg, **kw):
    return canonicalize(request(**kw), cfg)


def wait_for(jobs, key, status="done", t=5):
    end = time.time() + t
    while time.time() < end:
        s = jobs.status(key)
        if s and s["status"] == status:
            return s
        time.sleep(0.01)
    raise AssertionError(f"{key} never reached {status}: {jobs.status(key)}")


def test_a_run_goes_queued_running_done_and_is_cached(tmp_path):
    gate = threading.Event()
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine(gate=gate))
    t = jobs.submit(st(cfg), "c1")
    assert (t.status, t.cached) == ("queued", False)
    wait_for(jobs, t.key, "running")
    gate.set()
    done = wait_for(jobs, t.key)
    assert done["summary"]["video_bytes"] == 1000
    again = jobs.submit(st(cfg), "c2")
    assert (again.key, again.status, again.cached) == (t.key, "done", True)
    pool.shutdown()


def test_the_same_settings_while_running_share_one_run(tmp_path):
    gate = threading.Event()
    eng = FakeEngine(gate=gate)
    cfg, cache, jobs, pool = make(tmp_path, eng)
    tickets = [jobs.submit(st(cfg), f"c{i}") for i in range(5)]
    assert len({t.key for t in tickets}) == 1
    gate.set()
    wait_for(jobs, tickets[0].key)
    assert len(eng.calls) == 1
    pool.shutdown()


def test_cached_runs_cost_nothing_and_skip_the_rate_limit(tmp_path):
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine(), rate_per_minute=1)
    t = jobs.submit(st(cfg), "c1")
    wait_for(jobs, t.key)
    for _ in range(20):
        assert jobs.submit(st(cfg), "c1").cached
    pool.shutdown()


def test_rate_limit_per_client_with_a_window(tmp_path):
    now = [1000.0]
    cfg = config(tmp_path, rate_per_minute=2)
    cache = DiskCache(cfg.cache_dir, cfg.cache_max_bytes)
    pool = ThreadPoolExecutor(max_workers=2)
    jobs = Jobs(cfg, cache, pool, FakeEngine(), clock=lambda: now[0])
    jobs.submit(st(cfg, max_frames=100), "a")
    jobs.submit(st(cfg, max_frames=200), "a")
    with pytest.raises(RateLimited) as e:
        jobs.submit(st(cfg, max_frames=300), "a")
    assert 1 <= e.value.retry_after <= 61
    jobs.submit(st(cfg, max_frames=300), "b")                # another client is not affected
    now[0] += 61
    jobs.submit(st(cfg, max_frames=300), "a")                # the window has passed
    pool.shutdown()


def test_queue_is_bounded(tmp_path):
    gate = threading.Event()
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine(gate=gate), queue_max=3, workers=1)
    keys = [jobs.submit(st(cfg, max_frames=100 + i), f"c{i}").key for i in range(3)]
    with pytest.raises(QueueFull):
        jobs.submit(st(cfg, max_frames=500), "z")
    assert jobs.queue_depth() == 3
    gate.set()
    for k in keys:
        wait_for(jobs, k)
    assert jobs.queue_depth() == 0
    jobs.submit(st(cfg, max_frames=500), "z")                 # room again
    pool.shutdown()


def test_positions_count_down(tmp_path):
    gate = threading.Event()
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine(gate=gate), workers=1, queue_max=10)
    keys = [jobs.submit(st(cfg, max_frames=100 + i), f"c{i}").key for i in range(3)]
    assert [jobs.status(k)["position"] for k in keys] == [0, 1, 2]
    gate.set()
    wait_for(jobs, keys[-1])
    pool.shutdown()


def test_a_failed_run_is_reported_not_cached_and_can_be_retried(tmp_path):
    eng = FakeEngine(fail="boom")
    cfg, cache, jobs, pool = make(tmp_path, eng)
    t = jobs.submit(st(cfg), "c")
    s = wait_for(jobs, t.key, "failed")
    assert "boom" in s["error"]
    assert cache.keys() == [] and not cache.tmp(t.key).exists()
    eng.fail = None
    again = jobs.submit(st(cfg), "c")
    assert again.status == "queued"
    wait_for(jobs, again.key)
    pool.shutdown()


def test_unknown_key_has_no_status(tmp_path):
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine())
    assert jobs.status("nope") is None
    pool.shutdown()


def test_finished_entries_are_not_remembered_forever(tmp_path):
    from fly_mario_fly.lite import jobs as J
    cfg, cache, jobs, pool = make(tmp_path, FakeEngine(fail="x"), queue_max=10_000, rate_per_minute=10**6)
    for i in range(J.KEEP_FINISHED + 40):
        t = jobs.submit(st(cfg, max_frames=100 + i), "c")
        wait_for(jobs, t.key, "failed")
    assert len(jobs.jobs) <= J.KEEP_FINISHED + 1
    pool.shutdown()
