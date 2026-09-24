# What this file does, in plain English:
# Figures out which kinds of enemy/object get a live, editable smell
# control and which ones are shown greyed out, by reading the same JSON
# file the simulation itself reads -- instead of a hand-maintained list
# living inside the tab's own code.
"""tool/core/entity_registry.py -- tool/SPEC_ui_retro.md section 10:
"live" vs "greyed" is DERIVED from bridge/profiles/default.json (every
kind with a non-empty odours list is live, everything else is greyed),
not the hand-maintained LIVE_KINDS/GREYED_KINDS lists enemies.py/
objects.py used to carry. Adding a kind to that JSON with real odour
entries makes it live with no edit to either tab file -- this module's
own dummy-entry test proves it.
"""

from __future__ import annotations

from dataclasses import dataclass

from mario.entities.kinds import EntityKind
from tool.core.entity_profiles_store import load_default_raw

# A greyed kind's card must state WHY it's greyed (tool/SPEC_ui_retro.md
# section 7), not just that it's disabled -- the same reasons objects.py's
# old GREYED_KINDS table gave. A kind with an empty odours list and no
# entry here still gets a generic, honest fallback reason.
_GREYED_REASONS: dict[str, str] = {
    "GROUND": "No odours; looming/danger unread.",
    "USED_BLOCK": "No odours; looming/danger unread.",
    "SOLID_OTHER": "No odours; looming/danger unread.",
    "PIT": "Not yet a call site in the decision loop.",
}

# tool/assets/manifest.json's own ids (section 9) -- one per live kind;
# a kind absent here still gets an id (falls back through load_asset's
# own placeholder, never a KeyError).
_ASSET_IDS: dict[str, str] = {
    "GOOMBA": "goomba_card", "KOOPA": "koopa_card", "ENEMY": "enemy_card",
    "POWERUP": "powerup_card", "QUESTION_BLOCK": "question_block_card",
}


@dataclass(frozen=True)
class EntityKindEntry:
    kind: EntityKind
    display_name: str
    live: bool
    greyed_reason: str | None  # None when live
    asset_id: str


def _display_name(kind: EntityKind) -> str:
    return kind.name.replace("_", " ").title()


def all_entity_entries(default_raw: dict | None = None) -> list[EntityKindEntry]:
    """One entry per kind actually present in `default_raw` (real
    bridge/profiles/default.json when None, or a test-local override
    shaped the same way -- section 10's own dummy-entry test). A kind
    absent from the JSON entirely (EMPTY, today) gets no entry, matching
    bridge/entity_profiles.EntityProfiles.get()'s own "no entry = silent"
    behaviour."""
    raw = default_raw if default_raw is not None else load_default_raw()
    entries = []
    for key, kind_dict in raw.items():
        kind = EntityKind[key]
        live = len(kind_dict.get("odours", [])) > 0
        reason = None if live else _GREYED_REASONS.get(key, f"{_display_name(kind)}: no odours.")
        entries.append(EntityKindEntry(
            kind=kind, display_name=_display_name(kind), live=live,
            greyed_reason=reason, asset_id=_ASSET_IDS.get(key, f"{key.lower()}_card"),
        ))
    return entries


def entry_for(kind: EntityKind, default_raw: dict | None = None) -> EntityKindEntry:
    by_kind = {e.kind: e for e in all_entity_entries(default_raw)}
    return by_kind[kind]
