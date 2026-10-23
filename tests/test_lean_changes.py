"""Evolution tab data: each changed parameter carries the sense or action it belongs to; no old name is left in the web app."""
from dataclasses import replace
from pathlib import Path

from fly_mario_fly.api import jobs as J
from fly_mario_fly.api import knobs as K
from fly_mario_fly.runner import load_fly

ROOT = Path(__file__).resolve().parents[1]


def test_knob_changes_name_the_owner_in_words():
    start = load_fly("champion_e1s")
    best = replace(start, knobs={**start.knobs, "sour_smell.gain": 3.9, "jump.ttmn_thresh": 0.01})
    rows = {c.key: c for c in J.knob_changes(start, best, ["sour_smell.gain", "jump.ttmn_thresh"])}
    assert rows["sour_smell.gain"].owner == "Sour smell" and rows["jump.ttmn_thresh"].owner == "Jump"
    assert all(not any(ch.isdigit() for ch in c.words) for c in rows.values())


def test_every_knob_has_an_owner():
    assert set(K.owners_by_key()) == set(K.specs_by_key())


def test_the_web_app_has_one_name_and_no_stills_or_side_by_side():
    text = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "web" / "src").rglob("*") if p.suffix in (".ts", ".tsx", ".css") and p.name != "types.ts")
    assert "fly_mario_fly" in text and "stills" not in text.lower() and "side_by_side" not in text
