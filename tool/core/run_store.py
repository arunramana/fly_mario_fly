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
                info: dict, run_spec_snapshot: dict, batch_id: str | None = None,
                extra: dict | None = None) -> None:
    """`info` is run_steering.main()'s own summary dict -- `mb_weights`
    (a numpy array, not JSON-safe) is dropped from the stored copy; every
    other key is a plain number/bool/string. `batch_id`: None for a
    single Play; a shared string for every seed of one run_batch() call
    (tool/core/batch.py) -- "batch runs appear as a group in the run
    drawer" (ease-of-use redesign) needs this to actually group them,
    since nothing else in a run's own record says it came from a batch.
    `extra`: further top-level keys on the entry -- training runs add
    `group` ("Training · real") and `training` (network/episode/max_x/...)
    so the player's dropdown and the Learning tab can group them.
    Training entries store a compact `run_spec` ({"ref": <number>, ...}),
    resolved by `resolve_run_spec`, so 600 episodes don't each carry a
    full config snapshot in an index that is rewritten on every record."""
    path = _index_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = _read_index(project_name)
    entry = {
        "number": number,
        "slug": slug,
        "seed": seed,
        "git_commit": git_commit(),
        "time": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "summary": {k: v for k, v in info.items() if k != "mb_weights"},
        "run_spec": run_spec_snapshot,
    }
    if extra:
        entry.update(extra)
    entries.append(entry)
    path.write_text(json.dumps(entries, indent=2, sort_keys=True, default=str), encoding="utf-8")


def list_runs(project_name: str) -> list[dict]:
    return _read_index(project_name)


def patch_run(project_name: str, number: int, summary: dict | None = None,
              extra: dict | None = None) -> None:
    """Update one recorded run in place: merge `summary` into its summary
    (e.g. raw_frames_path=None when its frames are deleted) and `extra`
    into the entry itself."""
    entries = _read_index(project_name)
    for e in entries:
        if e["number"] == number:
            if summary:
                e["summary"].update(summary)
            if extra:
                e.update(extra)
            break
    else:
        raise ValueError(f"no run #{number} recorded for project {project_name!r}")
    _index_path(project_name).write_text(
        json.dumps(entries, indent=2, sort_keys=True, default=str), encoding="utf-8")


def resolve_run_spec(entry: dict, entries: list[dict] | None = None,
                     project_name: str | None = None) -> dict:
    """The full RunSpec dict for an entry, following a compact
    {"ref": <number>, "overrides": {...}} to the run whose spec it shares.
    Overrides: `shuffle_seed`, `learning_rate`, `max_frames`."""
    spec = entry.get("run_spec") or {}
    if "ref" not in spec:
        return spec
    if entries is None:
        entries = _read_index(project_name)
    base = next(e for e in entries if e["number"] == spec["ref"])
    full = json.loads(json.dumps(resolve_run_spec(base, entries)))
    ov = spec.get("overrides", {})
    if "shuffle_seed" in ov:
        full["tool_settings"]["circuits"]["shuffle_seed"] = ov["shuffle_seed"]
    if ov.get("learning_rate") is not None:
        full["config"]["mushroom_body"]["learning_rate"] = ov["learning_rate"]
    if "max_frames" in ov:
        full["config"]["scenario"]["max_frames"] = ov["max_frames"]
    return full


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
        f"learning_enabled={tool_settings.experiment.learning_enabled}, "
        f"brain_weights={tool_settings.experiment.brain_weights or 'fresh'}.\n\n"
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
        zf.writestr("config.json", json.dumps(resolve_run_spec(entry, entries), indent=2, sort_keys=True))
        for arcname, path in candidates.items():
            if path is not None and path.exists():
                zf.write(path, arcname)
    return bundle_path
