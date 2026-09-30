"""tool/core/run_spec.py -- RunSpec: everything one run needs, frozen, so
one object reproduces it (tool/PLAN.md section 3 and ground rule 5).
"""

from __future__ import annotations

import base64
import dataclasses
import hashlib
import zlib
from dataclasses import dataclass

from config.project_config import ProjectConfig
from config.project_config import from_dict as project_config_from_dict
from tool.core.tool_settings import ToolSettings
from tool.core.tool_settings import from_dict as tool_settings_from_dict


@dataclass(frozen=True)
class RunSpec:
    project_name: str
    config: ProjectConfig
    tool_settings: ToolSettings
    seed: int
    out_filename: str  # e.g. "029_my_run.mp4" -- tool/core/run_store.py assigns the number
    # Everything outside config/tool_settings that a run reads (docs/SPEC_bio_strict.md phase 1): the merged entity
    # profiles, the start state's action log, the brain-weights checksum. None = an older spec: live project files.
    snapshot: dict | None = None

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "config": self.config.to_dict(),
            "tool_settings": self.tool_settings.to_dict(),
            "seed": self.seed,
            "out_filename": self.out_filename,
            "snapshot": self.snapshot,
        }

    @staticmethod
    def from_dict(data: dict) -> RunSpec:
        return RunSpec(
            project_name=data["project_name"],
            config=project_config_from_dict(data["config"]),
            tool_settings=tool_settings_from_dict(data["tool_settings"]),
            seed=data["seed"],
            out_filename=data["out_filename"],
            snapshot=data.get("snapshot"),
        )


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def freeze(spec: RunSpec) -> RunSpec:
    """`spec` with its snapshot filled from the project's files as they are NOW, so the spec alone reproduces the
    run: merged entity profiles (only if enabled), the start state's action log, the brain-weights checksum."""
    from tool.core.entity_profiles_store import merged_raw
    from tool.core.savestates import load_state
    from tool.core.training import checkpoint_dir

    snap: dict = {}
    if spec.tool_settings.entity_profile.enabled:
        snap["entity_profiles"] = merged_raw(spec.project_name)
    exp = spec.tool_settings.experiment
    if exp.start_state:
        state = load_state(spec.project_name, exp.start_state)
        raw = state["actions"].astype("uint8").tobytes()
        snap["start_state"] = {"name": exp.start_state, "frame": state["frame"], "level": state["level"],
                               "source_run": state["source_run"], "sha256": sha256_of(raw),
                               "actions_b64": base64.b64encode(zlib.compress(raw)).decode("ascii")}
    if exp.brain_weights:
        data = (checkpoint_dir(spec.project_name) / exp.brain_weights).read_bytes()
        snap["brain_weights"] = {"name": exp.brain_weights, "sha256": sha256_of(data)}
    return dataclasses.replace(spec, snapshot=snap)


def snapshot_start_state(spec: RunSpec) -> dict | None:
    """The start state recorded in the snapshot as {name, frame, level, source_run, actions (uint8 array)}, or None."""
    import numpy as np
    s = (spec.snapshot or {}).get("start_state")
    if s is None:
        return None
    raw = zlib.decompress(base64.b64decode(s["actions_b64"]))
    if sha256_of(raw) != s["sha256"]:
        raise ValueError(f"snapshot start state {s['name']!r} is corrupt (checksum mismatch)")
    return {"name": s["name"], "frame": s["frame"], "level": s["level"], "source_run": s["source_run"],
            "actions": np.frombuffer(raw, dtype=np.uint8).copy()}
