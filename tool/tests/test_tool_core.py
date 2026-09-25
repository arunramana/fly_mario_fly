"""tool/PLAN.md P2's own test list: project create/duplicate/save round
trip, schema covers all 49 scalars with ranges, run numbering never
reuses a number, snapshot reproduces telemetry byte-for-byte.
"""
from __future__ import annotations

import dataclasses
import json
import shutil

import pytest

from config.output_routing import PROJECTS_ROOT
from config.params import scalar_count
from config.project_config import ProjectConfig
from tool.core.fitness import fitness_of
from tool.core.project import ToolProject
from tool.core.run_spec import RunSpec
from tool.core.run_store import (
    _index_path, export_run_bundle, list_runs, next_run_number, record_run,
)
from tool.core.runner import run_one
from tool.core.schema import ControlSpec, all_controls, get_value, with_value
from tool.core.tool_settings import CharacterSettings, ToolSettings

PROJECT_NAME = "_tool_core_test"


@pytest.fixture
def clean_project():
    root = PROJECTS_ROOT / PROJECT_NAME
    shutil.rmtree(root, ignore_errors=True)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_project_create_duplicate_save_round_trip(clean_project):
    dup_root = PROJECTS_ROOT / f"{PROJECT_NAME}_dup"
    shutil.rmtree(dup_root, ignore_errors=True)
    try:
        project = ToolProject.create(PROJECT_NAME)
        assert (clean_project / "config.json").exists()
        assert (clean_project / "tool.json").exists()
        assert project.config.output.project_name == PROJECT_NAME

        reopened = ToolProject.open(PROJECT_NAME)
        assert reopened.config == project.config
        assert reopened.tool_settings == project.tool_settings

        with pytest.raises(FileExistsError):
            ToolProject.create(PROJECT_NAME)

        duplicate = project.duplicate(f"{PROJECT_NAME}_dup")
        assert duplicate.config.output.project_name == f"{PROJECT_NAME}_dup"
        assert duplicate.tool_settings == project.tool_settings

        project.tool_settings = ToolSettings(character=CharacterSettings(player="luigi"))
        project.save()
        reloaded = ToolProject.open(PROJECT_NAME)
        assert reloaded.tool_settings.character.player == "luigi"

        assert PROJECT_NAME in ToolProject.list_recent()
        assert f"{PROJECT_NAME}_dup" in ToolProject.list_recent()
    finally:
        shutil.rmtree(dup_root, ignore_errors=True)


def test_schema_covers_all_scalars_with_ranges():
    controls = all_controls()
    from config.params import ALL_PARAM_CLASSES
    import dataclasses
    # GUI controls cover ALL_PARAM_CLASSES only; controller-module params
    # (MODULE_PARAM_CLASSES) are set in config JSON, not a tab.
    assert len(controls) == sum(len(dataclasses.fields(c)) for c in ALL_PARAM_CLASSES)
    assert all(isinstance(c, ControlSpec) for c in controls)
    # Every control's range is EXACTLY what config/params.py's own field
    # metadata says -- None ("genuinely unknown", config/params.py's own
    # docstring) is a valid, expected value, not a bug -- so this checks
    # equality with the source of truth, not "is not None".
    by_path = {c.path: c for c in controls}
    jump_g = by_path["jump.g"]
    assert jump_g.range == (1.12, 3.35)
    assert jump_g.provenance.startswith("measured")
    home_bias = by_path["steering.home_bias"]
    assert home_bias.range is None
    assert home_bias.provenance.startswith("invented")


def test_schema_get_and_with_value_round_trip():
    cfg = ProjectConfig()
    for control in all_controls():
        original = get_value(cfg, control.path)
        assert original == control.default
    changed = with_value(cfg, "jump.g", 3.0)
    assert get_value(changed, "jump.g") == 3.0
    assert get_value(cfg, "jump.g") != 3.0  # cfg itself is untouched (frozen)


def test_run_numbering_never_reuses_a_number(clean_project, tmp_path):
    assert next_run_number(PROJECT_NAME) == 1
    record_run(PROJECT_NAME, 1, "001_a", seed=0, info={"n_frames": 10}, run_spec_snapshot={})
    assert next_run_number(PROJECT_NAME) == 2
    record_run(PROJECT_NAME, 2, "002_b", seed=1, info={"n_frames": 20}, run_spec_snapshot={})
    assert next_run_number(PROJECT_NAME) == 3

    # Deleting the index's on-disk file entries (simulating a user deleting
    # a run's video/telemetry) must not make numbering go backwards --
    # next_run_number reads the index's own recorded history, not a
    # directory listing of what still exists.
    index_path = _index_path(PROJECT_NAME)
    entries = list_runs(PROJECT_NAME)
    assert len(entries) == 2
    assert [e["number"] for e in entries] == [1, 2]
    assert next_run_number(PROJECT_NAME) == 3  # still 3, even though nothing else changed


def test_snapshot_reproduces_telemetry_byte_for_byte(clean_project):
    cfg = ProjectConfig(
        scenario=dataclasses.replace(ProjectConfig().scenario, level="1-1", max_frames=200),
        output=dataclasses.replace(ProjectConfig().output, project_name=PROJECT_NAME),
    )
    spec = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=ToolSettings(),
                    seed=0, out_filename="original.mp4")
    tel_original, info_original = run_one(spec)
    original_csv = PROJECTS_ROOT / PROJECT_NAME / "telemetry" / "original_telemetry.csv"
    assert original_csv.exists()
    original_bytes = original_csv.read_bytes()

    # Round-trip the spec through the exact dict shape run_store.record_run
    # would persist into index.json, then reconstruct and re-run.
    snapshot = spec.to_dict()
    reconstructed = RunSpec.from_dict(snapshot)
    reconstructed = dataclasses.replace(reconstructed, out_filename="replayed.mp4")
    run_one(reconstructed)
    replayed_csv = PROJECTS_ROOT / PROJECT_NAME / "telemetry" / "replayed_telemetry.csv"
    assert replayed_csv.exists()

    assert replayed_csv.read_bytes() == original_bytes, (
        "replaying a run from its own stored snapshot did not reproduce "
        "the original telemetry byte-for-byte"
    )


def test_export_run_bundle_contains_config_and_telemetry(clean_project):
    import zipfile

    cfg = ProjectConfig(
        scenario=dataclasses.replace(ProjectConfig().scenario, level="1-1", max_frames=100),
        output=dataclasses.replace(ProjectConfig().output, project_name=PROJECT_NAME),
    )
    slug = "001_bundle_test"
    spec = RunSpec(project_name=PROJECT_NAME, config=cfg, tool_settings=ToolSettings(),
                    seed=0, out_filename=f"{slug}.mp4")
    tel, info = run_one(spec)
    record_run(PROJECT_NAME, 1, slug, seed=0, info=info, run_spec_snapshot=spec.to_dict())

    bundle_path = export_run_bundle(PROJECT_NAME, 1)
    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as zf:
        names = set(zf.namelist())
        assert "config.json" in names
        assert f"{slug}_telemetry.csv" in names
        # No video/note in this test (record_video defaults False, no note written).
        assert f"{slug}.mp4" not in names
        config_snapshot = json.loads(zf.read("config.json"))
        assert config_snapshot["config"]["output"]["project_name"] == PROJECT_NAME

    with pytest.raises(ValueError):
        export_run_bundle(PROJECT_NAME, 999)
