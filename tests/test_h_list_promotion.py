"""docs/CODE_AUDIT.md section H, promoted into config/params.py: proves
each new scalar is actually READ from the passed config, not just
declared -- the same "no control lies" bar every other config field in
this project is held to. Defaults are checked for byte-identical
telemetry against the pre-promotion golden by tests/test_golden.py
itself (nothing here duplicates that); this file only checks that a
NON-default value visibly changes something.
"""
from __future__ import annotations

import dataclasses

import numpy as np

import run_steering
from bridge.entity_profiles import load as load_profiles
from bridge.perception import profiled_enemy_thetas
from config.project_config import ProjectConfig
from mario.entities.kinds import EntityKind
from mario.entities.record import EntityRecord

SCENARIO = dict(level="1-1", max_frames=300, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def _run(config):
    return run_steering.main(out_mp4="/tmp/h_list_test.mp4", config=config, **SCENARIO)


def test_avers_presence_gate_changes_avoid_odor_telemetry():
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg)

    # Raising the gate far above any real aversive signal must suppress
    # avoid_odor entirely -- a direct, predictable behavioural change.
    huge_gate_cfg = dataclasses.replace(
        default_cfg, odour=dataclasses.replace(default_cfg.odour, avers_presence_gate=1e6))
    tel_huge_gate, _ = _run(huge_gate_cfg)

    assert tel_default["avoid_odor"].any(), "the default scenario never avoided odour at all -- test needs a real encounter"
    assert not tel_huge_gate["avoid_odor"].any(), "an impossibly high presence gate should suppress every avoid_odor frame"


def test_denormal_flush_threshold_changes_h_mbon_telemetry():
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg)

    # A huge threshold flushes essentially everything in h_mbon to zero
    # every frame, changing the mushroom-body bias terms that feed
    # steering -- detectable in dna01/dna02.
    huge_flush_cfg = dataclasses.replace(
        default_cfg, network=dataclasses.replace(default_cfg.network, denormal_flush_threshold=1e6))
    tel_huge_flush, _ = _run(huge_flush_cfg)

    assert not tel_default["dna01"].equals(tel_huge_flush["dna01"]), (
        "an aggressive denormal_flush_threshold produced identical dna01 telemetry"
    )


def test_stomp_distance_px_changes_stomp_count():
    default_cfg = ProjectConfig()
    _, info_default = _run(default_cfg)

    # A zero-width stomp window should count fewer (or equal) stomps than
    # a very generous one -- monotonic in the expected direction.
    zero_cfg = dataclasses.replace(
        default_cfg, interaction=dataclasses.replace(default_cfg.interaction, stomp_distance_px=0))
    _, info_zero = _run(zero_cfg)
    wide_cfg = dataclasses.replace(
        default_cfg, interaction=dataclasses.replace(default_cfg.interaction, stomp_distance_px=1000))
    _, info_wide = _run(wide_cfg)

    assert info_zero["n_stomps"] <= info_default["n_stomps"] <= info_wide["n_stomps"]
    assert info_zero["n_stomps"] < info_wide["n_stomps"], (
        "stomp_distance_px=0 vs 1000 produced the same stomp count -- the field isn't reaching the check"
    )


def test_mbon_dna02_frac_changes_dna02_telemetry():
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg)

    boosted_cfg = dataclasses.replace(
        default_cfg, mushroom_body=dataclasses.replace(
            default_cfg.mushroom_body, mbon_dna02_frac_l=0.5, mbon_dna02_frac_r=0.5))
    tel_boosted, _ = _run(boosted_cfg)

    assert not tel_default["dna02"].equals(tel_boosted["dna02"]), (
        "boosting mbon_dna02_frac_l/r 100x+ produced identical dna02 telemetry"
    )


def test_kc_projection_seed_changes_mb_proj_and_default_reproduces_original():
    """n_mb_sensory/kc_features_per_cell/kc_projection_seed default to
    exactly what was hardcoded before promotion (7, 3, 0) -- this is
    the direct proof, not an inference from the golden gate staying
    green: build the projection two ways and compare the array itself."""
    from bridge.full_policy import FullPolicy

    default_policy = FullPolicy(config=ProjectConfig())
    rng = np.random.default_rng(0)
    expected_proj = np.zeros((default_policy.n_kc, 7))
    for i in range(default_policy.n_kc):
        feats = rng.choice(7, size=3, replace=False)
        expected_proj[i, feats] = 1.0
    assert np.array_equal(default_policy.mb_proj, expected_proj), (
        "the default (config-driven) KC projection no longer matches what "
        "np.random.default_rng(0).choice(7, size=3) built before promotion"
    )

    different_seed_cfg = dataclasses.replace(
        ProjectConfig(), mushroom_body=dataclasses.replace(
            ProjectConfig().mushroom_body, kc_projection_seed=1))
    different_seed_policy = FullPolicy(config=different_seed_cfg)
    assert not np.array_equal(default_policy.mb_proj, different_seed_policy.mb_proj), (
        "kc_projection_seed=1 built the identical projection as seed=0"
    )


def test_question_block_odor_entity_width_px_reads_config():
    """de-duplication, not a new scalar (docs/CODE_AUDIT.md's own "do not
    merge" section): question_block_odor's *16 now reads
    config.entity.entity_width_px directly."""
    default_cfg = ProjectConfig()
    tel_default, _ = _run(default_cfg)

    wide_cfg = dataclasses.replace(
        default_cfg, entity=dataclasses.replace(default_cfg.entity, entity_width_px=200))
    tel_wide, _ = _run(wide_cfg)

    assert not tel_default["odor_l"].equals(tel_wide["odor_l"]) or \
        not tel_default["odor_r"].equals(tel_wide["odor_r"]), (
        "entity_width_px=200 produced identical food-odour telemetry -- "
        "question_block_odor isn't reading the config value"
    )
