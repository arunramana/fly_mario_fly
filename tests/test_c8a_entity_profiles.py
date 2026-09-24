"""docs/SPEC_entity_perception.md (C8a): per-kind gains on the two
existing aggregate signals (visual looming, food odour, threat odour),
opt-in via FullPolicy(entity_profiles=None|EntityProfiles). Two required
backward-compatibility tests (SPEC section 2), not one: entity_profiles=
None must reproduce today's telemetry, AND a profile loaded from
bridge/profiles/default.json alone (no override) must ALSO reproduce it
-- proving the new code path is numerically neutral at today's implicit
defaults, not just algebraically expected to be.
"""
from __future__ import annotations

import numpy as np
import pytest

import run_steering
from bridge.entity_profiles import EntityProfiles, KindProfile, OdourChannel, load as load_profiles
from bridge.perception import profiled_enemy_thetas
from mario.entities.kinds import EntityKind
from mario.entities.record import EntityRecord

SCENARIO = dict(level="1-1", max_frames=300, sigma=0.0, seed=0,
                 record_video=False, write_telemetry=False)


def test_load_with_no_override_matches_default_json():
    profiles = load_profiles(project_root=None)
    goomba = profiles.get(EntityKind.GOOMBA)
    assert goomba.danger_weight == 1.0
    assert goomba.looming_salience == 1.0
    assert len(goomba.odours) == 1
    assert goomba.odours[0].channel == "threat_goomba"
    assert goomba.odours[0].sign == -1
    assert goomba.odours[0].hunger_gated is False
    assert goomba.odours[0].intensity == 1.0


def test_load_with_partial_override_falls_back_correctly(tmp_path):
    (tmp_path / "entity_profiles.json").write_text(
        '{"GOOMBA": {"danger_weight": 2.0}}', encoding="utf-8")
    profiles = load_profiles(project_root=tmp_path)

    goomba = profiles.get(EntityKind.GOOMBA)
    assert goomba.danger_weight == 2.0  # overridden
    assert goomba.looming_salience == 1.0  # untouched, falls back to default.json
    assert len(goomba.odours) == 1  # untouched
    assert goomba.odours[0].channel == "threat_goomba"

    koopa = profiles.get(EntityKind.KOOPA)
    assert koopa.danger_weight == 1.0  # a different kind, entirely untouched


def test_load_with_unknown_kind_in_override_raises(tmp_path):
    (tmp_path / "entity_profiles.json").write_text(
        '{"GOOMBAA": {"danger_weight": 2.0}}', encoding="utf-8")
    with pytest.raises(ValueError, match="GOOMBAA"):
        load_profiles(project_root=tmp_path)


def test_load_with_no_override_file_present_equals_default_only(tmp_path):
    profiles_no_file = load_profiles(project_root=tmp_path)  # tmp_path has no entity_profiles.json
    profiles_none = load_profiles(project_root=None)
    assert profiles_no_file.get(EntityKind.GOOMBA) == profiles_none.get(EntityKind.GOOMBA)


def test_entity_profiles_none_reproduces_default_exactly(tmp_path):
    tel_default, _ = run_steering.main(out_mp4=str(tmp_path / "default.mp4"), **SCENARIO)
    tel_explicit_none, _ = run_steering.main(out_mp4=str(tmp_path / "none.mp4"),
                                              entity_profiles=None, **SCENARIO)
    assert tel_default.equals(tel_explicit_none), (
        "entity_profiles=None (explicit) differs from leaving it out -- the "
        "new argument isn't purely additive"
    )


def test_default_profile_reproduces_none_exactly(tmp_path):
    """The stronger of the two required tests (SPEC section 2): the NEW
    profiled_enemy_thetas/profiled_odor code path, fed nothing but
    bridge/profiles/default.json's own shipped values, must compute
    byte-identical telemetry to the OLD code path being bypassed
    entirely -- not just "close," actually equal."""
    tel_none, _ = run_steering.main(out_mp4=str(tmp_path / "none.mp4"), **SCENARIO)
    profiles = load_profiles(project_root=None)
    tel_default_profile, _ = run_steering.main(
        out_mp4=str(tmp_path / "profiled.mp4"), entity_profiles=profiles, **SCENARIO)
    assert tel_none.equals(tel_default_profile), (
        "a profile loaded from bridge/profiles/default.json alone produced "
        "different telemetry to entity_profiles=None -- the profiled_* "
        "functions are not neutral at today's implicit defaults"
    )


def test_modified_danger_weight_changes_telemetry(tmp_path):
    """danger_weight is a per-kind MASTER knob over both looming and
    threat odour (SPEC section 1) -- raising GOOMBA's must move both the
    jump circuit's TTMn (fed by scaled theta) and the steering circuit's
    aversive odour."""
    default_profiles = load_profiles(project_root=None)
    boosted_goomba = KindProfile(
        odours=tuple(
            OdourChannel(c.channel, c.sign, c.hunger_gated, intensity=1.4)
            for c in default_profiles.get(EntityKind.GOOMBA).odours
        ),
        looming_salience=default_profiles.get(EntityKind.GOOMBA).looming_salience,
        danger_weight=2.0,
        is_food=default_profiles.get(EntityKind.GOOMBA).is_food,
        body_scale=default_profiles.get(EntityKind.GOOMBA).body_scale,
    )
    modified = EntityProfiles(by_kind={**default_profiles.by_kind, EntityKind.GOOMBA: boosted_goomba})

    tel_default, _ = run_steering.main(
        out_mp4=str(tmp_path / "default.mp4"), entity_profiles=default_profiles, **SCENARIO)
    tel_modified, _ = run_steering.main(
        out_mp4=str(tmp_path / "modified.mp4"), entity_profiles=modified, **SCENARIO)

    assert not tel_default["ttmn"].equals(tel_modified["ttmn"]), (
        "boosting GOOMBA's danger_weight produced identical TTMn telemetry "
        "-- the profile isn't reaching the jump circuit's looming input"
    )
    assert not tel_default["avers_r"].equals(tel_modified["avers_r"]), (
        "boosting GOOMBA's danger_weight produced identical aversive-odour "
        "telemetry -- the profile isn't reaching the threat-odour pathway"
    )


class _FakeRegistry:
    def __init__(self, records):
        self._records = records

    def enemy_records(self, ram):
        return self._records


def test_scaled_theta_clamped_at_pi():
    """A synthetic looming_salience*danger_weight product large enough to
    push the raw angle past pi must clamp there, not report a physically
    meaningless angle (SPEC section 1.1)."""
    huge_kind_profile = KindProfile(
        odours=(), looming_salience=100.0, danger_weight=100.0, is_food=False, body_scale=1.0,
    )
    profiles = EntityProfiles(by_kind={EntityKind.GOOMBA: huge_kind_profile})
    registry = _FakeRegistry([
        EntityRecord(kind=EntityKind.GOOMBA, x=20, y=None, width=16,
                     height=None, active=True, traits=frozenset()),
    ])
    # Close enough (mario_x=16, d=4) that the raw angle is already large;
    # a 100*100 multiplier would otherwise send it far past pi.
    theta, _dtheta, _d_out = profiled_enemy_thetas(
        ram=None, mario_x=16, prev_theta={"L": 0.0, "R": 0.0}, registry=registry, profiles=profiles)
    assert theta["R"] == pytest.approx(np.pi)
    assert theta["R"] <= np.pi
