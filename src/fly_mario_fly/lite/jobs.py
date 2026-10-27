"""The queue: one run per cache key, a bounded line of waiting runs, a rate limit per client.

    submit(settings, client) -> Ticket   cached | already queued/running (same ticket) | new (queued)
    status(key)             -> dict      {status: queued|running|done|failed, position, frame, ...}

`pool` is a thread pool (its size is the number of runs at once) and `engine(settings_json, out, progress, cfg_json) -> summary`
the function each thread calls: in production a ProcessEngine (one run in a worker process), in tests a fake.
Nothing here knows about HTTP.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from fly_mario_fly.lite.cache import DiskCache
from fly_mario_fly.lite.config import LiteConfig
from fly_mario_fly.lite.settings import Settings

KEEP_FINISHED = 200            # finished / failed entries remembered for status calls (done ones are found in the cache anyway)


class RateLimited(RuntimeError):
    def __init__(self, retry_after: int):
        super().__init__(f"too many new runs; try again in {retry_after} s")
        self.retry_after = retry_after


class QueueFull(RuntimeError):
    pass


@dataclass
class Ticket:
    key: str
    status: str                # "done" (cached) | "queued" | "running"
    cached: bool


class Jobs:
    def __init__(self, cfg: LiteConfig, cache: DiskCache, pool, engine, clock=time.monotonic):
        self.cfg, self.cache, self.pool, self.engine, self.clock = cfg, cache, pool, engine, clock
        self.lock = threading.RLock()       # re-entrant: a future that is already done calls _done inside submit
        self.jobs: "OrderedDict[str, dict]" = OrderedDict()     # key -> {status, error, ...}, oldest first
        self.hits: dict = defaultdict(deque)                    # client -> times of its recent new runs

    # ---- submit -----------------------------------------------------------------------------------------------
    def submit(self, st: Settings, client: str = "") -> Ticket:
        key = st.key(self.cfg.version)
        if self.cache.get(key) is not None:
            return Ticket(key, "done", True)
        with self.lock:
            job = self.jobs.get(key)
            if job is not None and job["status"] in ("queued", "running"):
                return Ticket(key, job["status"], False)             # the same run is already on its way: share it
            self._rate_check(client)
            if self._active() >= self.cfg.queue_max:
                raise QueueFull(f"the server is busy ({self._active()} runs waiting); try again in a minute")
            self.jobs.pop(key, None)
            self.jobs[key] = {"status": "queued", "error": None, "progress": self.cache.dir / f"{key}.progress"}
            self._forget_old()
            self.hits[client].append(self.clock())
            fut = self.pool.submit(self._work, key, st)
            fut.add_done_callback(lambda f, k=key: self._done(k, f))
        return Ticket(key, "queued", False)

    def _active(self) -> int:
        return sum(1 for j in self.jobs.values() if j["status"] in ("queued", "running"))

    def _rate_check(self, client: str) -> None:
        q, now = self.hits[client], self.clock()
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.cfg.rate_per_minute:
            raise RateLimited(int(60 - (now - q[0])) + 1)
        if len(self.hits) > 5000:                                   # only clients with a recent run are kept
            for c in [c for c, d in self.hits.items() if not d]:
                self.hits.pop(c, None)

    def _forget_old(self) -> None:
        finished = [k for k, j in self.jobs.items() if j["status"] in ("done", "failed")]
        for k in finished[:-KEEP_FINISHED]:
            self.jobs.pop(k, None)

    # ---- the worker side --------------------------------------------------------------------------------------
    def _work(self, key: str, st: Settings) -> dict:
        with self.lock:
            self.jobs[key]["status"] = "running"
        prog = self.jobs[key]["progress"]
        out = self.cache.tmp(key)
        try:
            return self.engine(st.to_json(), str(out), str(prog), self.cfg.worker_json())
        except BaseException:
            Path(out).unlink(missing_ok=True)
            raise
        finally:
            Path(prog).unlink(missing_ok=True)

    def _done(self, key: str, fut) -> None:
        with self.lock:
            job = self.jobs.get(key)
            if job is None:
                return
            try:
                summary = fut.result()
                self.cache.put(key, summary)
                job["status"] = "done"
            except BaseException as e:                              # a failed run is reported, never cached
                job["status"], job["error"] = "failed", f"{type(e).__name__}: {e}"

    # ---- status -----------------------------------------------------------------------------------------------
    def status(self, key: str):
        """None for a key nobody has seen. Otherwise a dict with `status`, and `position` (0 = running / next) while waiting."""
        summary = self.cache.get(key)
        if summary is not None:
            return {"status": "done", "summary": summary}
        with self.lock:
            job = self.jobs.get(key)
            if job is None:
                return None
            out = {"status": job["status"], "error": job["error"]}
            if job["status"] in ("queued", "running"):
                waiting = [k for k, j in self.jobs.items() if j["status"] in ("queued", "running")]
                out["position"] = waiting.index(key)
                try:
                    out["frame"] = int(job["progress"].read_text())
                except (OSError, ValueError):
                    out["frame"] = 0
            return out

    def queue_depth(self) -> int:
        with self.lock:
            return self._active()
