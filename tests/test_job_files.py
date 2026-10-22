"""The files a job process and the API share: atomic writes that survive a reader holding the file, and reads that
survive a file being swapped (Windows: PermissionError / WinError 32 on replace)."""
import json
import os
import threading

import pytest

from fly_mario.runner import atomic


def test_replace_retries_on_permission_error_then_succeeds(tmp_path, monkeypatch):
    src, dst = tmp_path / "a.tmp", tmp_path / "a"
    src.write_text("x")
    real, calls = os.replace, []

    def flaky(s, d):
        calls.append(1)
        if len(calls) < 5:
            raise PermissionError(32, "being used by another process")
        return real(s, d)
    monkeypatch.setattr(os, "replace", flaky)
    atomic.replace_retry(src, dst, delay=0)
    assert len(calls) == 5 and dst.read_text() == "x"


def test_replace_gives_up_after_the_tries(tmp_path, monkeypatch):
    def locked(s, d):
        raise PermissionError(32, "locked")
    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(PermissionError):
        atomic.replace_retry(tmp_path / "a", tmp_path / "b", tries=3, delay=0)


def test_a_half_written_or_missing_file_reads_as_none_only_after_retrying(tmp_path):
    p = tmp_path / "job.json"
    assert atomic.read_json(p) is None                                # missing: at once
    p.write_text('{"status": "run')                                   # half-written
    assert atomic.read_json(p, tries=3, delay=0) is None

    def finish():
        p.write_text('{"status": "running"}')
    threading.Timer(0.1, finish).start()
    assert atomic.read_json(p) == {"status": "running"}               # read again until the writer is done


def test_readers_never_see_a_dead_job_while_two_writers_replace_the_file_many_times(tmp_path):
    """Readers hammering job.json while two writers (the API and the job process) swap it 400 times each."""
    p = tmp_path / "job.json"
    atomic.write_json(p, {"status": "running", "n": 0})
    stop, bad, errors = threading.Event(), [], []

    def reader():
        while not stop.is_set():
            try:
                j = atomic.read_json(p)
                if j is None or j.get("status") != "running":
                    bad.append(j)
                stop.wait(0.001)                                          # hammering, but not a spin that never lets go of the file
            except Exception as e:                                    # noqa: BLE001
                errors.append(e)

    def writer(k):
        try:
            for i in range(400):
                atomic.write_json(p, {"status": "running", "n": i, "by": k})
        except Exception as e:                                        # noqa: BLE001
            errors.append(e)

    readers = [threading.Thread(target=reader) for _ in range(3)]
    writers = [threading.Thread(target=writer, args=(k,)) for k in range(2)]
    for t in readers + writers:
        t.start()
    for t in writers:
        t.join()
    stop.set()
    for t in readers:
        t.join()
    assert errors == [] and bad == []
    assert json.loads(p.read_text())["status"] == "running"
    assert [f.name for f in tmp_path.iterdir()] == ["job.json"]       # no temp files left behind
