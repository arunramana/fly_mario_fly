"""tool/core/run_store.py -- NNN numbering, index.json, run history
(tool/PLAN.md section 3: projects/<name>/tool_runs/index.json). The
number never repeats, even if an earlier run's files were deleted -- it
reads the index's own recorded maximum, never a directory listing.
"""

from __future__ import annotations

import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from config.output_routing import PROJECTS_ROOT


def _index_path(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / "tool_runs" / "index.json"


def _read_index(project_name: str) -> list[dict]:
    path = _index_path(project_name)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def next_run_number(project_name: str) -> int:
    entries = _read_index(project_name)
    if not entries:
        return 1
    return max(e["number"] for e in entries) + 1


def git_commit() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                 text=True, check=True, cwd=Path(__file__).parent.parent.parent)
        return result.stdout.strip()
    except Exception:
        return None


def record_run(project_name: str, number: int, slug: str, seed: int,
                info: dict, run_spec_snapshot: dict, batch_id: str | None = None) -> None:
    """`info` is run_steering.main()'s own summary dict -- `mb_weights`
    (a numpy array, not JSON-safe) is dropped from the stored copy; every
    other key is a plain number/bool/string. `batch_id`: None for a
    single Play; a shared string for every seed of one run_batch() call
    (tool/core/batch.py) -- "batch runs appear as a group in the run
    drawer" (ease-of-use redesign) needs this to actually group them,
    since nothing else in a run's own record says it came from a batch."""
    path = _index_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _read_index(project_name)
    entries.append({
        "number": number,
        "slug": slug,
        "seed": seed,
        "git_commit": git_commit(),
        "time": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "summary": {k: v for k, v in info.items() if k != "mb_weights"},
        "run_spec": run_spec_snapshot,
    })
    path.write_text(json.dumps(entries, indent=2, sort_keys=True, default=str), encoding="utf-8")


def list_runs(project_name: str) -> list[dict]:
    return _read_index(project_name)


def write_run_note(project_name: str, number: int, slug: str, seed: int,
                    config, tool_settings, info: dict) -> Path:
    """`projects/<name>/runs/NNN_slug.md`, CLAUDE.md's own convention --
    setup and numbers filled in; the user adds the "what we learned" line
    (tool/PLAN.md P4, decision 2: the tool never appends to docs/RUNS.md,
    only writes this)."""
    path = PROJECTS_ROOT / project_name / "runs" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    cancelled_note = " **CANCELLED before it finished.**" if info.get("cancelled") else ""
    text = (
        f"# {number:03d} -- {slug}{cancelled_note}\n\n"
        f"**Setup.** Level {config.scenario.level}, seed {seed}, "
        f"sigma={config.noise.sigma}, max_frames={config.scenario.max_frames}, "
        f"player={tool_settings.character.player}, "
        f"shuffle_seed={tool_settings.circuits.shuffle_seed}, "
        f"hunger_override={tool_settings.character.hunger_override}, "
        f"learning_enabled={tool_settings.experiment.learning_enabled}.\n\n"
        f"**What happened.**{cancelled_note} {info.get('n_frames')} frames, "
        f"died_or_flagged={info.get('died_or_flagged')}, "
        f"max_x_abs={info.get('max_x_abs')}, score={info.get('score')}.\n\n"
        f"**What we learned.** _(fill in)_\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


def export_run_bundle(project_name: str, number: int) -> Path:
    """One zip with everything needed to hand a single run to someone else
    or archive it outside the project: the frozen RunSpec (config.json),
    telemetry CSV, video (if `record_video` was on), and the run note (if
    written) -- tool/PLAN.md P7. Written next to the run's own files, at
    `projects/<name>/runs/NNN_slug_bundle.zip`.
    """
    entries = _read_index(project_name)
    matches = [e for e in entries if e["number"] == number]
    if not matches:
        raise ValueError(f"no run #{number} recorded for project {project_name!r}")
    entry = matches[0]
    slug = entry["slug"]
    project_root = PROJECTS_ROOT / project_name

    bundle_path = project_root / "runs" / f"{slug}_bundle.zip"
    bundle_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = {
        "config.json": None,  # written from run_spec below, not a file on disk
        f"{slug}_telemetry.csv": project_root / "telemetry" / f"{slug}_telemetry.csv",
        f"{slug}.mp4": project_root / "runs" / f"{slug}.mp4",
        f"{slug}.md": project_root / "runs" / f"{slug}.md",
    }

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.json", json.dumps(entry["run_spec"], indent=2, sort_keys=True))
        for arcname, path in candidates.items():
            if path is not None and path.exists():
                zf.write(path, arcname)
    return bundle_path
