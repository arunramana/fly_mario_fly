"""The web app lists things in a fixed order (enemies, objects, power-ups). The order lives in configs/object_order.yaml, the API serves it
as `order`, and the screens sort by it; the web code names no plug-in."""
from pathlib import Path

import yaml

from fly_mario_fly import registry
from fly_mario_fly.api import convert

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "enemies": ["goomba", "koopa", "piranha", "hammer_bro", "buzzy_beetle", "podoboo", "red_koopa"],
    "objects": ["pipe", "step", "pit", "qblock", "usedblock", "brick", "ceiling_block"],
    "powerups": ["mushroom", "fire_flower", "one_up", "star", "coin"],
}
KINDS = {"enemies": {"enemy"}, "objects": {"terrain", "obstacle"}, "powerups": {"pickup"}}


def served():
    return {o.name: o.order for o in convert.registry_info([], []).objects}


def test_the_configured_order_is_the_requested_one():
    assert yaml.safe_load((ROOT / "configs" / "object_order.yaml").read_text(encoding="utf-8")) == EXPECTED


def test_the_api_serves_each_tab_in_that_order():
    orders = served()
    for tab, names in EXPECTED.items():
        assert sorted(names, key=orders.get) == names, tab
        assert len({orders[n] for n in names}) == len(names)


def test_tabs_follow_the_requested_sequence_enemies_then_objects_then_powerups():
    orders = served()
    flat = [n for names in EXPECTED.values() for n in names]
    assert sorted(flat, key=orders.get) == flat


def test_every_name_is_a_registered_plugin_in_the_tab_its_kind_belongs_to():
    plugins = registry.list_plugins("objects")
    for tab, names in EXPECTED.items():
        for n in names:
            assert plugins[n].kind in KINDS[tab], (tab, n, plugins[n].kind)


def test_every_registered_object_is_listed_so_a_new_plugin_is_not_forgotten():
    assert set(registry.list_plugins("objects")) == {n for names in EXPECTED.values() for n in names}, \
        "add the new plug-in to configs/object_order.yaml"


def test_an_unlisted_type_comes_after_the_listed_ones(monkeypatch):
    monkeypatch.setattr(convert, "_object_ranks", lambda: {"goomba": 0})
    orders = served()
    assert orders["goomba"] == 0 and all(v >= 1 for n, v in orders.items() if n != "goomba")
    assert sorted(orders.values()) == sorted(set(orders.values()))               # still distinct, in the registry's order


def test_the_screens_sort_by_the_apis_order_and_name_no_plugin():
    screens = ROOT / "web" / "src" / "screens"
    assert "byOrder(reg.objects.filter((o) => tabOf(o) === tab))" in (screens / "FlyScreen.tsx").read_text(encoding="utf-8")
    assert "byOrder(reg.objects.filter((o) => m.on_screen" in (screens / "MomentScreen.tsx").read_text(encoding="utf-8")
    assert "objOrder(a) - objOrder(b)" in (screens / "SceneScreen.tsx").read_text(encoding="utf-8")
