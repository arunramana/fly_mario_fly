"""tool/SPEC_ui_retro.md section 10: "adding an entity needs no UI code."
tool/core/entity_registry.py derives live/greyed from a default.json-
shaped dict rather than enemies.py/objects.py's old hand-maintained
LIVE_KINDS/GREYED_KINDS lists. Proven here with EntityKind.EMPTY -- a
real enum member neither tab file has ever mentioned by name, since
bridge/profiles/default.json has no entry for it today -- given a
test-local override dict that adds one.
"""
from __future__ import annotations

from bridge.entity_profiles import EntityProfiles, load as load_profiles
from mario.entities.kinds import EntityKind
from tool.core.entity_profiles_store import load_default_raw
from tool.core.entity_registry import all_entity_entries, entry_for


def _default_raw_plus_dummy(odours: list) -> dict:
    raw = dict(load_default_raw())
    raw["EMPTY"] = {
        "odours": odours, "looming_salience": 0.0, "danger_weight": 0.0,
        "is_food": False, "body_scale": 1.0,
    }
    return raw


def test_a_dummy_entry_with_odours_is_derived_live():
    dummy_raw = _default_raw_plus_dummy(
        [{"channel": "dummy_test_channel", "sign": 1, "hunger_gated": False, "intensity": 1.0}]
    )
    entry = entry_for(EntityKind.EMPTY, dummy_raw)
    assert entry.live is True
    assert entry.greyed_reason is None


def test_a_dummy_entry_with_no_odours_is_derived_greyed_with_a_reason():
    dummy_raw = _default_raw_plus_dummy([])
    entry = entry_for(EntityKind.EMPTY, dummy_raw)
    assert entry.live is False
    assert entry.greyed_reason  # non-empty -- a greyed card must say why, not just that it's off


def test_real_default_json_is_unaffected_by_the_dummy_override():
    """The dummy only exists in the test-local dict passed in -- the real
    bridge/profiles/default.json (and every other kind's classification)
    is untouched."""
    real_entries = {e.kind: e for e in all_entity_entries()}
    assert EntityKind.EMPTY not in real_entries
    assert real_entries[EntityKind.GOOMBA].live is True
    assert real_entries[EntityKind.PIT].live is False


def test_a_card_renders_for_the_dummy_entry_with_no_edit_to_enemies_or_objects_py(qapp):
    """tool/ui/widgets/entity_cards.EntityCardGrid is the SAME generic
    widget enemies.py/objects.py both use -- this passes it a dummy entry
    directly, proving the rendering path itself is data-driven, not just
    the classification."""
    from tool.ui.widgets.entity_cards import EntityCardGrid

    dummy_raw = _default_raw_plus_dummy(
        [{"channel": "dummy_test_channel", "sign": 1, "hunger_gated": False, "intensity": 1.0}]
    )
    entry = entry_for(EntityKind.EMPTY, dummy_raw)
    profiles = EntityProfiles(by_kind={
        **load_profiles(project_root=None).by_kind,
        EntityKind.EMPTY: _kind_profile_from_entry(dummy_raw["EMPTY"]),
    })

    grid = EntityCardGrid(
        [entry], profiles, enabled=True,
        on_intensity_changed=lambda *_: None, on_sign_changed=lambda *_: None,
        on_field_changed=lambda *_: None,
    )
    assert EntityKind.EMPTY in grid._card_buttons
    assert grid._card_buttons[EntityKind.EMPTY].text() == "Empty"
    assert EntityKind.EMPTY in grid._kind_boxes
    assert EntityKind.EMPTY in grid._valence_checks  # live -- got the full detail panel, not a greyed stub


def _kind_profile_from_entry(d: dict):
    from bridge.entity_profiles import KindProfile, OdourChannel
    return KindProfile(
        odours=tuple(OdourChannel(o["channel"], o["sign"], o["hunger_gated"], o.get("intensity", 1.0))
                     for o in d.get("odours", [])),
        looming_salience=d.get("looming_salience", 0.0), danger_weight=d.get("danger_weight", 0.0),
        is_food=d.get("is_food", False), body_scale=d.get("body_scale", 1.0),
    )
