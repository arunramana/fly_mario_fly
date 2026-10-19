"""The fly's plug-ins and group table are consistent (no data needed)."""
import numpy as np
import pytest

from fly_mario import contracts, registry
from fly_mario.fly import groups
from fly_mario.fly.spec import BrainSpec

MECHS = registry.list_plugins("mechanisms")


def test_the_five_circuits_exist():
    assert set(MECHS) == {"escape", "hearing", "attraction", "aversion", "walking"}


@pytest.mark.parametrize("name", sorted(MECHS))
def test_mechanism_fits_the_contract_and_names_real_groups(name):
    m = MECHS[name]
    assert isinstance(m, contracts.Mechanism)
    table = groups.load_groups()
    for g in [*m.input_groups, *m.output_groups, *m.neuron_sets]:
        assert g in table, f"{name}: {g} is not in groups.yaml"


def test_extra_neurons_have_distinct_build_order():
    orders = [m.build_order for m in MECHS.values() if m.extra is not None]
    assert len(orders) == len(set(orders)) == 3


def test_aversion_is_read_only_and_the_others_write():
    assert not MECHS["aversion"].extra.writes_into_base
    assert MECHS["hearing"].extra.writes_into_base and MECHS["attraction"].extra.writes_into_base


def test_group_masks_split_hemispheres():
    types = np.array(["LC4", "LC4", "DNa01", "DNa02", "ORN_DM1", "ORN_DC4", "JO-B1_a", "TTMn"], dtype="U40")
    sides = np.array(["L", "R", "L", "R", "L", "L", "", ""], dtype="U40")
    m = groups.masks_for(types, sides)
    assert m["LC4_L"].tolist() == [True, False] + [False] * 6
    assert m["DNa_R"].sum() == 1 and m["DNa_L"].sum() == 1
    assert m["ORN_L"].sum() == 1 and m["DC4_L"].sum() == 1     # the sour receptor is not an attractive one
    assert m["JO"].sum() == 1
    assert "MDN" not in m                                      # a group with no neuron in this brain is absent


def test_unknown_mechanism_is_an_error(tmp_path, monkeypatch):
    from fly_mario.fly import brain
    monkeypatch.setenv("FLY_MARIO_DATA", str(tmp_path))
    with pytest.raises(ValueError, match="unknown mechanism"):
        brain.brain_name(BrainSpec(mechanisms=("nope",)))


def test_spec_order_does_not_change_the_brain_name(tmp_path, monkeypatch):
    from fly_mario.fly import brain
    monkeypatch.setenv("FLY_MARIO_DATA", str(tmp_path))
    a = brain.brain_name(BrainSpec(mechanisms=("aversion", "hearing")))
    assert a == brain.brain_name(BrainSpec(mechanisms=("hearing", "aversion", "escape"))) == "steer636+hearing+aversion"
