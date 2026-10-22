"""The job process: an evolution or a "test this fly", run in its own process, in its own folder.

    $FLY_MARIO_DATA/runs/<job id>/
        job.json        what was asked and where the job stands: kind, status, fly, level, dials, generations ...
        progress.json   updated as it goes: phase, generation, best / mean fitness, ETA (evolve); episodes done, ETA (test)
        result.json     a finished job's answer (test: the dev-set result per dials; evolve: the dev set on the best fly)
        log.txt         the job process's output
        alive           touched every few seconds while the process lives (a job that stops touching it was interrupted)
        (evolve also: config.json, fly.yaml, start.yaml, best.yaml, dev.json, state.pkl, from search.py)

`python -m fly_mario.evolve job <folder>` runs `run_job`. The API writes job.json, starts that command and later
stops it; it never imports this package (api/jobs.py), so nothing the API does can block on a job.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from fly_mario.evolve import devset, search
from fly_mario.runner import atomic
from fly_mario.runner import config as C

ALIVE_EVERY = 5.0           # seconds between heartbeats


def _write(path: Path, data) -> None:
    atomic.write_json(path, data)


def read_json(path: Path):
    return atomic.read_json(path)


def flag_x_for(level: str) -> float:
    """The level's flag x (what progress is divided by): the scan's, else the furthest a winning run reached."""
    return search.resolve_flag_x(level, None)


def _heartbeat(folder: Path, stop: threading.Event) -> None:
    while not stop.is_set():
        (folder / "alive").write_text(str(time.time()))
        stop.wait(ALIVE_EVERY)


def run_job(folder) -> int:
    """Run the job in `folder` to the end and record how it went in job.json."""
    folder = Path(folder)
    job = read_json(folder / "job.json")
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(folder, stop), daemon=True).start()
    job.update(status="running", pid=os.getpid(), started=time.time())
    _write(folder / "job.json", job)
    try:
        result = _evolve(folder, job) if job["kind"] == "evolve" else _test(folder, job)
        _write(folder / "result.json", result)
        job = read_json(folder / "job.json")
        if job["status"] != "cancelled":
            job.update(status="finished", finished=time.time())
            _write(folder / "job.json", job)
        return 0
    except BaseException as e:                                # noqa: BLE001 - the job's last word, whatever went wrong
        job = read_json(folder / "job.json") or job
        job.update(status="failed", error=f"{type(e).__name__}: {e}", finished=time.time())
        _write(folder / "job.json", job)
        raise
    finally:
        stop.set()


def _test(folder: Path, job: dict) -> dict:
    """Play the fly on the level's dev set at each requested dials setting; progress counts episodes."""
    fly = C.fly_from_dict(job["fly_config"])
    which = ["original", "tuned"] if job["dials"] == "both" else [job["dials"]]
    n_each = len(devset.dev_starts(job["level"]))
    total, t0 = n_each * len(which), time.time()
    pool = search.Pool(job["workers"])
    out: dict = {}
    try:
        for k, dials in enumerate(which):
            def tick(i, n, k=k):
                done = k * n_each + i
                el = time.time() - t0
                _write(folder / "progress.json", {"phase": "testing", "done": done, "total": total,
                                                  "elapsed_s": round(el), "eta_s": round(el / done * (total - done)),
                                                  "updated": time.time()})
            out[dials] = devset.evaluate(fly, job["level"], dials, pool=pool, flag_x=1.0, on_done=tick)
    finally:
        pool.close()
    _write(folder / "progress.json", {"phase": "done", "done": total, "total": total, "elapsed_s": round(time.time() - t0),
                                      "eta_s": 0, "updated": time.time()})
    return {"results": out}


def _evolve(folder: Path, job: dict) -> dict:
    """CMA-ES from the fly (at the dials asked for), elitist, then the dev set on the best fly (search.run does both)."""
    fly = devset.with_dials(C.fly_from_dict(job["fly_config"]), job["dials"])
    (folder / "fly.yaml").write_text(C.dump_fly(fly), encoding="utf-8")
    start = job["start"]
    cfg = {"id": job["id"], "folder": str(folder), "fly": str(folder / "fly.yaml"), "level": job["level"],
           "gens": job["generations"], "seed": job["seed"], "pop": job["pop"], "workers": job["workers"],
           "moments": [] if start in ("level_start", None) else [start], "train_n": job["train_n"],
           "flag_x": job.get("flag_x") or flag_x_for(job["level"])}
    out = search.run(cfg, log=lambda s: print(s, flush=True))
    return {"best_generation": out["best"]["gen"], "dev": {k: v["summary"] for k, v in out["dev"].items()},
            "best_fly": "best.yaml"}
