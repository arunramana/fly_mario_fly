"""Background jobs as the API sees them: one folder per job under the runs folder, one process per job.

The API never imports the evolve package (the boundary rule). It writes job.json, starts
`python -m fly_mario.evolve job <folder>`, reads progress.json / result.json as the job writes them, and stops the
job's process tree to cancel. Nothing here waits for a job, so no request ever blocks on one.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Optional

from fly_mario import runner
from fly_mario.api import convert as V
from fly_mario.api import knobs as K
from fly_mario.api import schemas as S
from fly_mario.contracts import FlyConfig

STALE_AFTER = 45.0          # a "running" job silent for this long was interrupted (the job touches `alive` every 5 s)
SRC = str(Path(__file__).resolve().parents[2])


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    tmp.replace(path)


def kill_tree(pid: int) -> None:
    """Stop the process `pid` and every process it started (its episode workers). Only that PID's tree."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


# ---- knob changes, in words --------------------------------------------------------------------------------------
def change_words(spec, before: float, after: float) -> tuple:
    """(words, direction) for a knob that went from `before` to `after`: how far along its own slider, in words."""
    if spec.kind == "switch":
        a, b = K.to_position(spec, before) >= 0.5, K.to_position(spec, after) >= 0.5
        return ("about the same", "same") if a == b else (f"switched to {spec.hi_label if b else spec.lo_label}", "hi" if b else "lo")
    d = K.to_position(spec, after) - K.to_position(spec, before)
    m = abs(d)
    if m < 0.03:
        return "about the same", "same"
    how = "a bit" if m < 0.12 else "clearly" if m < 0.3 else "much"
    end = spec.hi_label if d > 0 else spec.lo_label
    return f"{how} toward {end}", "hi" if d > 0 else "lo"


def knob_changes(start: FlyConfig, best: FlyConfig, keys: list) -> list:
    """What evolution changed, one row per knob it was free to move. Words only."""
    specs = K.specs_by_key()
    was, now = runner.resolve_knobs(start), runner.resolve_knobs(best)
    out = []
    for key in keys:
        if key not in specs or key not in was or key not in now:
            continue
        words, direction = change_words(specs[key], was[key], now[key])
        s = specs[key]
        out.append(S.KnobChange(key=key, label=s.label, lo_label=s.lo_label, hi_label=s.hi_label, words=words, direction=direction))
    return out


# ---- result shapes -----------------------------------------------------------------------------------------------
def _dev(d: dict | None) -> Optional[S.DevSetResult]:
    if not d:
        return None
    eps = []
    for i, e in enumerate(d.get("episodes", [])):
        c = e.get("counts") or {}
        eps.append(S.StartResult(label=f"start {i + 1}", outcome=e["outcome"], max_x=float(e["max_x"]), score=float(e["score"]),
                                 jumps=int(c.get("a_onsets", 0)), back_ups=int(c.get("left_presses", 0)),
                                 blocks=int(e.get("blocks") or 0), mushroom=bool(e.get("mushroom")),
                                 death=V.death_to_dto(e.get("death"))))
    return S.DevSetResult(flags=d["flags"], n=d["n"], mean_max_x=d["mean_max_x"], min_max_x=d["min_max_x"],
                          mean_score=d["mean_score"], episodes=eps)


def _progress(job: dict, prog: dict | None) -> S.JobProgress:
    p = prog or {}
    rows = [r for r in p.get("rows", []) if r["gen"] >= 0]
    return S.JobProgress(
        phase=p.get("phase", ""), generation=int(p.get("generation", 0)), generations=int(job.get("generations", 0)),
        done=int(p.get("done", 0)), total=int(p.get("total", 0)), best=p.get("best"), mean=p.get("mean"),
        eta_s=p.get("eta_s"), elapsed_s=int(p.get("elapsed_s", 0)),
        bars=[S.Generation(gen=r["gen"], best=r["best"], mean=r["mean"], best_ever=r["best_ever"]) for r in rows])


def _headline(job: dict, folder: Path) -> str:
    if job["status"] != "finished":
        return ""
    if job["kind"] == "test":
        res = (_read(folder / "result.json") or {}).get("results", {})
        names = (("original", "Original"), ("tuned", "Tuned"))
        return " · ".join(f"{label} {res[k]['summary']['flags']}/{res[k]['summary']['n']}" for k, label in names if k in res)
    res = _read(folder / "result.json") or {}
    b, s = res.get("dev", {}).get("best"), res.get("dev", {}).get("start")
    return f"{b['flags']}/{b['n']} on unseen starts (was {s['flags']}/{s['n']})" if b and s else ""


class Jobs:
    def __init__(self, runs_dir: Path, flies_dir: Path):
        self.dir, self.flies = Path(runs_dir), Path(flies_dir)
        self.procs: dict[str, subprocess.Popen] = {}

    # ---- starting and stopping ------------------------------------------------------------------------------
    def _check_level(self, level: str) -> None:
        if level not in {lv.id for lv in runner.level_catalogue(self.dir)}:
            raise ValueError(f"unknown level {level!r}")

    def create(self, kind: str, fly: FlyConfig, level: str, dials: str, generations: int = 0, start: str = "level_start",
               workers: Optional[int] = None, seed: int = 1, pop: int = 12, train_n: int = 0,
               flag_x: Optional[float] = None) -> str:
        self._check_level(level)
        if kind == "evolve":                    # progress is divided by the flag's x: it has to be known
            info = runner.level_info(level, self.dir)
            flag_x = flag_x or info.flag_x or (info.status.best_x if info.status.wins else None)
            if not flag_x:
                raise ValueError(f"level {level} has no known flag position yet (no run has reached it): "
                                 "play it through once first")
        jid = f"{'evo' if kind == 'evolve' else 'test'}_{time.strftime('%Y%m%d-%H%M%S')}_{fly.name}_{level}_{uuid.uuid4().hex[:4]}"
        folder = self.dir / jid
        folder.mkdir(parents=True, exist_ok=True)
        job = {"id": jid, "kind": kind, "status": "queued", "fly": fly.name, "fly_config": runner.fly_to_dict(fly),
               "level": level, "dials": dials, "generations": generations, "start": start,
               "workers": workers if workers is not None else min(8, os.cpu_count() or 1), "seed": seed, "pop": pop,
               "train_n": train_n, "flag_x": flag_x, "created": time.time(), "pid": None, "error": ""}
        _write(folder / "job.json", job)
        log = open(folder / "log.txt", "ab")
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [SRC, os.environ.get("PYTHONPATH")]))}
        p = subprocess.Popen([sys.executable, "-m", "fly_mario.evolve", "job", str(folder)], stdout=log,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, **kw)
        log.close()
        self.procs[jid] = p
        now = _read(folder / "job.json") or job                # the process may already have moved it on
        if now["status"] == "queued":
            _write(folder / "job.json", {**now, "status": "running", "pid": p.pid})
        return jid

    def cancel(self, jid: str) -> bool:
        folder = self._folder(jid)
        job = _read(folder / "job.json") if folder else None
        if job is None:
            return False
        if job["status"] in ("queued", "running"):
            pid = job.get("pid") or (self.procs[jid].pid if jid in self.procs else None)
            if pid:
                kill_tree(int(pid))
            job = _read(folder / "job.json") or job
            _write(folder / "job.json", {**job, "status": "cancelled", "finished": time.time()})
        return True

    # ---- reading --------------------------------------------------------------------------------------------
    def _folder(self, jid: str) -> Optional[Path]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", jid):
            return None
        f = self.dir / jid
        return f if (f / "job.json").exists() else None

    def _job(self, folder: Path) -> Optional[dict]:
        job = _read(folder / "job.json")
        if job is None:
            return None
        if job["status"] == "running":
            proc = self.procs.get(job["id"])
            beat = folder / "alive"
            last = beat.stat().st_mtime if beat.exists() else job["created"]
            if (proc is not None and proc.poll() is not None) or time.time() - last > STALE_AFTER:
                job = _read(folder / "job.json") or job                      # it may have just finished
                if job["status"] == "running":
                    job = {**job, "status": "failed", "error": job.get("error") or "interrupted: the job stopped without finishing"}
        return job

    def _summary(self, job: dict, folder: Path) -> S.JobSummary:
        what = "Evolution" if job["kind"] == "evolve" else "Test"
        return S.JobSummary(id=job["id"], kind=job["kind"], status=job["status"], fly=job["fly"], level_id=job["level"],
                            dials=job["dials"], created=job["created"], title=f"{what} of {job['fly']} on {job['level']}",
                            headline=_headline(job, folder), progress=_progress(job, _read(folder / "progress.json")))

    def list(self) -> list:
        out = []
        for p in self.dir.glob("*/job.json") if self.dir.exists() else ():
            job = self._job(p.parent)
            if job:
                out.append(self._summary(job, p.parent))
        return sorted(out, key=lambda s: s.created, reverse=True)

    def detail(self, jid: str) -> Optional[S.JobDetail]:
        folder = self._folder(jid)
        job = self._job(folder) if folder else None
        if job is None:
            return None
        d = S.JobDetail(**self._summary(job, folder).model_dump(), error=job.get("error", ""),
                        generations=job.get("generations", 0), start=job.get("start", "level_start"),
                        saved_as=job.get("saved_as"))
        res = _read(folder / "result.json") if job["status"] == "finished" else None
        if res and job["kind"] == "test":
            d.results = {k: _dev(v["summary"] | {"episodes": v["episodes"]}) for k, v in res["results"].items()}
        elif res:
            dev = _read(folder / "dev.json") or {}
            d.dev_best, d.dev_start = _dev(dev.get("best")), _dev(dev.get("start"))
            d.best_generation = res.get("best_generation")
            d.changes = self._changes(folder)
        return d

    def _changes(self, folder: Path) -> list:
        try:
            start = runner.load_fly(folder / "start.yaml")
            best = runner.load_fly(folder / "best.yaml")
        except (OSError, ValueError):
            return []
        return knob_changes(start, best, list(best.provenance.get("evolved", [])))

    def generation_fly(self, jid: str, gen: int) -> Optional[S.FlyDTO]:
        """The fly of one generation's best candidate: the start fly with that generation's knob values."""
        folder = self._folder(jid)
        prog = _read(folder / "progress.json") if folder else None
        if prog is None:
            return None
        row = next((r for r in prog["rows"] if r["gen"] == gen), None)
        if row is None:
            return None
        start = runner.load_fly(folder / "start.yaml")
        fly = replace(start, name=f"{start.name}_gen{gen}", knobs={**start.knobs, **row["best_values"]})
        return V.fly_to_dto(fly)

    def use(self, jid: str, name: str) -> Optional[str]:
        """Save the evolved fly as a new fly yaml (with provenance); returns its name. Raises FileExistsError for a taken name."""
        folder = self._folder(jid)
        if folder is None or not (folder / "best.yaml").exists():
            return None
        best = runner.load_fly(folder / "best.yaml")
        dev = (_read(folder / "dev.json") or {}).get("best")
        prov = {**best.provenance, "evolution": jid}
        if dev:
            prov["unseen_starts"] = f"reached the flag {dev['flags']} of {dev['n']} times"
        taken = lambda n: (self.flies / f"{n}.yaml").exists()                 # noqa: E731
        if name:
            if taken(name):
                raise FileExistsError(f"a fly named {name!r} already exists")
        else:
            name = best.name
            n = 2
            while taken(name):
                name, n = f"{best.name}_{n}", n + 1
        self.flies.mkdir(parents=True, exist_ok=True)
        (self.flies / f"{name}.yaml").write_text(runner.dump_fly(replace(best, name=name, provenance=prov)), encoding="utf-8")
        job = _read(folder / "job.json") or {}
        _write(folder / "job.json", {**job, "saved_as": name})
        return name
