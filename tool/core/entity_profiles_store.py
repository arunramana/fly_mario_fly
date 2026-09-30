"""tool/core/entity_profiles_store.py -- read/write
projects/<name>/entity_profiles.json for tabs 2-3's editor (tool/PLAN.md
P6, docs/SPEC_entity_perception.md section 6). Thin wrapper around
bridge/entity_profiles.py: that module loads/merges for a *run*; this one
also exposes the raw, un-merged override dict so the editor can show and
change just the kind/field a user actually touched, leaving everything
else to fall back to bridge/profiles/default.json as before.
"""

from __future__ import annotations

import json
from pathlib import Path

from config.output_routing import PROJECTS_ROOT
from bridge.entity_profiles import DEFAULT_PROFILE_PATH, EntityProfiles, load as load_profiles


def override_path(project_name: str) -> Path:
    return PROJECTS_ROOT / project_name / "entity_profiles.json"


def load_default_raw() -> dict:
    data = json.loads(DEFAULT_PROFILE_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_override_raw(project_name: str) -> dict:
    path = override_path(project_name)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_override_raw(project_name: str, data: dict) -> Path:
    path = override_path(project_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def set_kind_field(project_name: str, kind_name: str, field_name: str, value) -> None:
    """Sets one top-level field (`danger_weight`, `looming_salience`) on
    one kind, in the override file, leaving every other kind/field alone.
    `kind_name`/`field_name` are exactly `bridge/profiles/default.json`'s
    own keys."""
    override = load_override_raw(project_name)
    kind_override = dict(override.get(kind_name, {}))
    kind_override[field_name] = value
    override[kind_name] = kind_override
    save_override_raw(project_name, override)


def set_kind_odour_intensity(project_name: str, kind_name: str, odour_index: int, intensity: float) -> None:
    """Sets one odour-list entry's `intensity`. Overriding `odours`
    replaces the kind's whole list (bridge/entity_profiles.py's own merge
    rule), so this restates every field of every entry from the MERGED
    (default-or-already-overridden) profile, changing only `intensity` on
    the entry at `odour_index`."""
    from mario.entities.kinds import EntityKind
    merged = load_profiles(project_root=PROJECTS_ROOT / project_name)
    kind_profile = merged.get(EntityKind[kind_name])
    odours = [
        {"channel": o.channel, "sign": o.sign, "hunger_gated": o.hunger_gated,
         "intensity": intensity if i == odour_index else o.intensity}
        for i, o in enumerate(kind_profile.odours)
    ]
    override = load_override_raw(project_name)
    kind_override = dict(override.get(kind_name, {}))
    kind_override["odours"] = odours
    override[kind_name] = kind_override
    save_override_raw(project_name, override)


def set_kind_odour_sign(project_name: str, kind_name: str, odour_index: int, sign: int) -> None:
    """tool/SPEC_ui_retro.md section 4, the valence flip: sets one
    odour-list entry's `sign` (+1 attractive / -1 aversive), the same
    restate-the-whole-list pattern as set_kind_odour_intensity above.
    Runtime needs no change -- bridge/perception.py's profiled_odor
    already routes by `odour.sign` per entry (SPEC section 1.2/1.3), so a
    flipped GOOMBA (sign=+1) moves its concentration into the *food* sum
    instead of *threat*, using its own `intensity`; `danger_weight` then
    does nothing for that entry, since section 1's design only applies it
    to threat-signed channels."""
    from mario.entities.kinds import EntityKind
    merged = load_profiles(project_root=PROJECTS_ROOT / project_name)
    kind_profile = merged.get(EntityKind[kind_name])
    odours = [
        {"channel": o.channel, "sign": sign if i == odour_index else o.sign, "hunger_gated": o.hunger_gated,
         "intensity": o.intensity}
        for i, o in enumerate(kind_profile.odours)
    ]
    override = load_override_raw(project_name)
    kind_override = dict(override.get(kind_name, {}))
    kind_override["odours"] = odours
    override[kind_name] = kind_override
    save_override_raw(project_name, override)


def merged_raw(project_name: str) -> dict:
    from bridge.entity_profiles import merged_raw as _merged_raw
    return _merged_raw(PROJECTS_ROOT / project_name)


def load_merged(project_name: str) -> EntityProfiles:
    return load_profiles(project_root=PROJECTS_ROOT / project_name)
