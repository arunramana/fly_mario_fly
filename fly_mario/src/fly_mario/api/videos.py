"""Video exports as the API sees them: one folder per export under $FLY_MARIO_DATA/videos/, one process per stage.

Same shape as the evolution jobs (api/jobs.py): the API writes job.json, starts `python -m fly_mario.render job <folder>`,
reads progress.json / stills.json / info.json as the process writes them, and stops the process tree to cancel.
An export goes through two stages in the same folder: "stills" (2-3 PNGs, made as soon as the export is requested)
and "video" (the mp4, only after the user asks for it with `render`). Nothing here waits for a process.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fly_mario.api import schemas as S
from fly_mario.api.jobs import SRC, STALE_AFTER, _read, _write, kill_tree
from fly_mario.render import export as X
from fly_mario.render import specs as Sp

ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


class Videos:
    def __init__(self, runs_dir: Path, videos_dir: Optional[Path] = None):
        self.runs = Path(runs_dir)
        self.dir = Path(videos_dir) if videos_dir else self.runs.parent / "videos"
        self.procs: dict[str, subprocess.Popen] = {}

    # ---- asking for an export -----------------------------------------------------------------------------------
    def _side(self, ref: S.VideoSideRef) -> dict:
        if ref.run_id:
            return Sp.saved_side(ref.run_id, self.runs, ref.label)
        if ref.job_id:
            return Sp.test_side(ref.job_id, ref.start, ref.dials, self.runs, ref.label)
        raise ValueError("each side needs a run_id or a test job_id")

    def spec(self, req: S.VideoRequest) -> dict:
        """The export spec for a request. Raises ValueError (a 422) for anything that cannot be made."""
        if req.export == "run":
            if not req.run_id:
                raise ValueError("a run video needs a run_id")
            return Sp.run_spec(req.run_id, req.show_senses, True if req.show_brain is None else req.show_brain,
                               req.speed or 1, req.frame_from, req.frame_to, self.runs)
        if req.export == "side_by_side":
            if req.a is None or req.b is None:
                raise ValueError("a side-by-side needs two runs (a and b)")
            return Sp.side_by_side_spec(self._side(req.a), self._side(req.b), req.a.label, req.b.label,
                                        bool(req.show_brain), req.show_senses, req.speed or 1)
        if not req.job_id:
            raise ValueError("a montage needs the evolution's job_id")
        return Sp.montage_spec(req.job_id, req.generations or None, req.clip_seconds, req.speed or 2, req.include_start,
                               req.show_senses, self.runs)

    def create(self, req: S.VideoRequest) -> str:
        spec = self.spec(req)
        folder = X.new_job_folder(spec, Sp.title(spec), self.dir)
        self._start(folder, "stills")
        return folder.name

    def render(self, vid: str) -> bool:
        """Start the mp4 stage of an export whose stills have been made. False if there is no such export."""
        folder = self._folder(vid)
        job = self._job(folder) if folder else None
        if job is None:
            return False
        if job["status"] in ("queued", "running"):
            raise RuntimeError("this export is still working")
        if job["stage"] == "video" and job["status"] == "finished":
            return True                                              # already rendered
        self._start(folder, "video")
        return True

    def _start(self, folder: Path, stage: str) -> None:
        job = _read(folder / "job.json")
        _write(folder / "job.json", {**job, "stage": stage, "status": "queued", "error": "", "pid": None})
        (folder / "progress.json").unlink(missing_ok=True)
        log = open(folder / "log.txt", "ab")
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [SRC, os.environ.get("PYTHONPATH")]))}
        p = subprocess.Popen([sys.executable, "-m", "fly_mario.render", "job", str(folder)], stdout=log,
                             stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, **kw)
        log.close()
        self.procs[folder.name] = p
        now = _read(folder / "job.json") or job                      # the process may already have moved it on
        if now["status"] == "queued":
            _write(folder / "job.json", {**now, "status": "running", "pid": p.pid})

    def cancel(self, vid: str) -> bool:
        folder = self._folder(vid)
        job = _read(folder / "job.json") if folder else None
        if job is None:
            return False
        if job["status"] in ("queued", "running"):
            pid = job.get("pid") or (self.procs[vid].pid if vid in self.procs else None)
            if pid:
                kill_tree(int(pid))
            job = _read(folder / "job.json") or job
            _write(folder / "job.json", {**job, "status": "cancelled", "finished": time.time()})
            (folder / "video.part.mp4").unlink(missing_ok=True)     # the half-written file this export's process made
        return True

    # ---- reading -------------------------------------------------------------------------------------------------
    def _folder(self, vid: str) -> Optional[Path]:
        if not ID.match(vid):
            return None
        f = self.dir / vid
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
                job = _read(folder / "job.json") or job              # it may have just finished
                if job["status"] == "running":
                    job = {**job, "status": "failed", "error": job.get("error") or "interrupted: the export stopped without finishing"}
        return job

    def _summary(self, job: dict, folder: Path) -> S.VideoSummary:
        prog = _read(folder / "progress.json") or {}
        vid = job["id"]
        stills = (_read(folder / "stills.json") or {}).get("stills", [])
        info = _read(folder / "info.json") if job["stage"] == "video" and job["status"] == "finished" else None
        have_video = info is not None and (folder / info["file"]).exists()
        return S.VideoSummary(
            id=vid, export=job["export"], title=job["title"], status=job["status"], stage=job["stage"], created=job["created"],
            progress=S.VideoProgress(phase=prog.get("phase", ""), done=int(prog.get("done", 0)), total=int(prog.get("total", 0)),
                                     eta_s=prog.get("eta_s"), elapsed_s=int(prog.get("elapsed_s", 0))),
            stills=[f"/videos/{vid}/stills/{i + 1}.png" for i in range(len(stills))],
            video=f"/videos/{vid}/video.mp4" if have_video else None, error=job.get("error", ""),
            duration_s=info["duration_s"] if info else None, size_mb=round(info["bytes"] / 1e6, 1) if info else None,
            render_s=info["render_s"] if info else None,
            checks=[S.VideoCheck(label=c["label"], outcome=c["outcome"], max_x=c["max_x"], hash_ok=c["hash_ok"])
                    for c in (info or {}).get("replay_checks", [])])

    def list(self) -> list:
        out = []
        for p in self.dir.glob("*/job.json") if self.dir.exists() else ():
            job = self._job(p.parent)
            if job:
                out.append(self._summary(job, p.parent))
        return sorted(out, key=lambda s: s.created, reverse=True)

    def detail(self, vid: str) -> Optional[S.VideoSummary]:
        folder = self._folder(vid)
        job = self._job(folder) if folder else None
        return self._summary(job, folder) if job else None

    def still_path(self, vid: str, n: int) -> Optional[Path]:
        folder = self._folder(vid)
        p = folder / "stills" / f"still_{n}.png" if folder else None
        return p if p and p.exists() else None

    def video_path(self, vid: str) -> Optional[Path]:
        folder = self._folder(vid)
        p = folder / "video.mp4" if folder else None
        return p if p and p.exists() else None
