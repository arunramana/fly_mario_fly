"""The API sends death as {x, kind, object_type, object_label}; the runner's cause string is read only in convert."""
from fly_mario.api.convert import death_to_dto


def test_enemy_fall_other_and_none():
    e = death_to_dto({"x": 891, "cause": "enemy:koopa"})
    assert (e.kind, e.object_type, e.object_label, e.x) == ("enemy", "koopa", "Koopa", 891)
    f = death_to_dto({"x": 5, "cause": "pit"})
    assert (f.kind, f.object_type) == ("fall", "pit") and f.object_label
    o = death_to_dto({"x": 7, "cause": "other"})
    assert (o.kind, o.object_type, o.object_label) == ("other", None, None)
    assert death_to_dto(None) is None
