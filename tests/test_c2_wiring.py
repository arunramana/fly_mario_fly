"""tool/PLAN.md C2: NetworkParams, HabituationParams, EntityParams and
RetinotopyParams were documentation-only -- editing them in a project JSON
did not change an episode (docs/CODE_AUDIT.md S3). Each now drives the
live system through a constructor, not a module constant. One sensitivity
check per group: changing the config value must change telemetry (or, for
retinotopy -- permanently off by default -- must reach the function that
would use it, since a full retinotopic episode is a separate, closed
negative result, docs/RUNS.md 023-024).
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import run_steering
from config.project_config import ProjectConfig

SCENARIO = dict(level="1-1", max_frames=200, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def _run(config, tmp_path, name):
    return run_steering.main(out_mp4=str(tmp_path / name), config=config, **SCENARIO)


def test_network_substeps_changes_telemetry(tmp_path):
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg, tmp_path, "default.mp4")

    fewer_substeps = dataclasses.replace(default_cfg,
                                          network=dataclasses.replace(default_cfg.network, substeps=2))
    tel_fewer, _ = _run(fewer_substeps, tmp_path, "fewer.mp4")

    assert not tel_default["ttmn"].equals(tel_fewer["ttmn"]), (
        "changing network.substeps from 10 to 2 produced identical TTMn "
        "telemetry -- SUBSTEPS is still a module constant somewhere, not "
        "actually read from config"
    )


def test_network_clip_changes_telemetry(tmp_path):
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg, tmp_path, "default.mp4")

    low_clip = dataclasses.replace(default_cfg,
                                    network=dataclasses.replace(default_cfg.network, clip=5.0))
    tel_clip, _ = _run(low_clip, tmp_path, "clip.mp4")

    assert not tel_default["lc4"].equals(tel_clip["lc4"]), (
        "dropping network.clip from 50 to 5 produced identical LC4 "
        "telemetry -- CLIP is still a module constant somewhere"
    )


def test_habituation_give_up_reaches_the_reflex_objects():
    """A full episode rarely fires the escape/climb reflex often enough in
    a short run to observe habituation kick in either way (it needs
    repeated no-progress firings), so this checks the wiring directly:
    FullPolicy's own ReflexHabituation instances must carry the config
    value, not HAB_GIVE_UP/HAB_PROGRESS_PX's module defaults."""
    from bridge.full_policy import FullPolicy

    default_cfg = ProjectConfig()
    policy_default = FullPolicy(config=default_cfg, level="1-1")
    policy_default.reset(seed=0)
    assert policy_default.hab_escape.give_up == default_cfg.habituation.hab_give_up
    assert policy_default.hab_climb.give_up == default_cfg.habituation.hab_give_up

    custom_cfg = dataclasses.replace(
        default_cfg, habituation=dataclasses.replace(default_cfg.habituation, hab_give_up=1))
    policy_custom = FullPolicy(config=custom_cfg, level="1-1")
    policy_custom.reset(seed=0)
    assert policy_custom.hab_escape.give_up == 1, (
        "FullPolicy built hab_escape with the default give_up, not the "
        "one in the config it was constructed from"
    )
    assert policy_custom.hab_climb.give_up == 1


def test_entity_width_changes_telemetry(tmp_path):
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg, tmp_path, "default.mp4")

    wide_entities = dataclasses.replace(
        default_cfg, entity=dataclasses.replace(default_cfg.entity, entity_width_px=64))
    tel_wide, _ = _run(wide_entities, tmp_path, "wide.mp4")

    assert not tel_default["theta"].equals(tel_wide["theta"]), (
        "entity_width_px=64 vs the default 16 produced identical theta "
        "telemetry -- ENTITY_WIDTH_PX is still a module constant somewhere "
        "(theta = 2*arctan(width / (2*|d|)) depends on it directly)"
    )


def test_retinotopy_params_reach_the_functions():
    """retinotopic=False is permanent (docs/RUNS.md 023-024) so this checks
    the plumbing directly rather than through a full episode: the two
    functions RetinotopyParams documents accept and use the values, not
    just the module-level fallbacks. Skips if fly.sensing.retinotopy's own
    `mcns` dependency (../mcns.py, outside this package) isn't importable
    -- pre-existing: nothing in this suite has ever exercised this
    permanently-off, closed-negative-result module before."""
    pytest.importorskip("mcns")
    from fly.sensing.retinotopy import receptive_field_centers, azimuth_target
    import pandas as pd
    bodies = pd.DataFrame({"bodyId": [1, 2], "type": ["LC4", "LC4"], "somaSide": ["L", "R"]})
    rf_default = receptive_field_centers("LC4", bodies)
    rf_custom = receptive_field_centers("LC4", bodies, spread_fallback=99.0, spread_floor=0.5)
    assert not np.array_equal(rf_default["hex1_spread"], rf_custom["hex1_spread"]), (
        "a custom spread_fallback produced the same hex1_spread as the "
        "default -- receptive_field_centers isn't using its own parameter"
    )

    az_default = azimuth_target(64.0, hex1_origin=0.0, hex1_far=10.0)
    az_custom = azimuth_target(64.0, hex1_origin=0.0, hex1_far=10.0, d_ref=256.0)
    assert az_default != az_custom, (
        "a custom d_ref produced the same azimuth_target output as the "
        "default -- AZIMUTH_D_REF is still hard-coded somewhere"
    )
