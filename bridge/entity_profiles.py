# What this file does, in plain English:
# Loads bridge/profiles/default.json into typed objects, one per kind of
# thing the fly can smell or see (Goomba, Koopa, power-up, and so on), and
# optionally overlays a project's own tweaks to a few of those numbers on
# top -- anything the project doesn't mention keeps the shipped default.
"""bridge/entity_profiles.py -- C8a (docs/SPEC_entity_perception.md):
typed load/merge for bridge/profiles/default.json plus an optional
per-project override, projects/<name>/entity_profiles.json. Consumed by
bridge/perception.py's profiled_enemy_thetas()/profiled_odor(), only when
FullPolicy is given entity_profiles=<EntityProfiles>; None (default)
never touches this module at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from mario.entities.kinds import EntityKind

DEFAULT_PROFILE_PATH = Path(__file__).parent / "profiles" / "default.json"


@dataclass(frozen=True)
class OdourChannel:
    channel: str
    sign: int
    hunger_gated: bool
    intensity: float = 1.0


@dataclass(frozen=True)
class KindProfile:
    odours: tuple[OdourChannel, ...] = ()
    looming_salience: float = 0.0
    danger_weight: float = 0.0
    is_food: bool = False
    body_scale: float = 1.0


@dataclass(frozen=True)
class EntityProfiles:
    by_kind: dict[EntityKind, KindProfile] = field(default_factory=dict)

    def get(self, kind: EntityKind) -> KindProfile:
        """Any kind this file doesn't mention (EMPTY has no entry at all)
        gets the all-zero/no-odour default -- silent, not smelled, not
        looming, matching how an un-tracked kind behaves today."""
        return self.by_kind.get(kind, KindProfile())


def _load_raw(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _odour_from_dict(d: dict) -> OdourChannel:
    return OdourChannel(
        channel=d["channel"],
        sign=d["sign"],
        hunger_gated=d["hunger_gated"],
        intensity=d.get("intensity", 1.0),
    )


def _kind_profile_from_dict(d: dict) -> KindProfile:
    return KindProfile(
        odours=tuple(_odour_from_dict(o) for o in d.get("odours", [])),
        looming_salience=d.get("looming_salience", 0.0),
        danger_weight=d.get("danger_weight", 0.0),
        is_food=d.get("is_food", False),
        body_scale=d.get("body_scale", 1.0),
    )


def _merge_kind_dict(default_d: dict, override_d: dict) -> dict:
    """Per-field merge, except `odours`: an override's odour list replaces
    the kind's whole list rather than being merged entry-by-entry, so
    there's no ambiguous rule for matching one override entry to one
    default entry by position or channel name (SPEC section 2)."""
    return {**default_d, **override_d}


def load(project_root: str | Path | None = None) -> EntityProfiles:
    """`project_root=None`: `bridge/profiles/default.json` alone -- this
    is also what a project with no `entity_profiles.json` override file
    gets. Raises on an override file naming a kind `default.json` doesn't
    have -- a typo'd kind name must fail loudly, not silently no-op."""
    default_raw = _load_raw(DEFAULT_PROFILE_PATH)

    override_raw: dict = {}
    if project_root is not None:
        override_path = Path(project_root) / "entity_profiles.json"
        if override_path.exists():
            override_raw = _load_raw(override_path)

    unknown = set(override_raw) - set(default_raw)
    if unknown:
        raise ValueError(
            f"entity_profiles.json overrides unknown kind(s): {sorted(unknown)} "
            f"-- must be one of {sorted(default_raw)}"
        )

    by_kind = {
        EntityKind[key]: _kind_profile_from_dict(_merge_kind_dict(default_d, override_raw.get(key, {})))
        for key, default_d in default_raw.items()
    }
    return EntityProfiles(by_kind=by_kind)
