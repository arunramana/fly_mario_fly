"""Every dataclass in contracts.py can be built from simple values."""
from fly_mario_fly import contracts as c


def test_construct_all():
    box = c.Box(0, 0, 16, 16)
    mario = c.MarioState(10, 20, 14, 16, False, "small", 1)
    obj = c.ObjectInstance("goomba", 1, box, "ahead")
    knob = c.KnobSpec("k", "K", "lo", "hi", 1.0, 0.0, 2.0)
    step = c.CalcStep("theta", "2*atan(w/2d)", 0.3, 0.1)
    item = c.OverlayItem("box", (0, 0, 1, 1), "#fff")
    out = c.SenseOutput({"LC4": 0.5}, [item], {"gain": 1.0}, [step])
    scene = c.Scene("1-2")
    fly = c.FlyConfig("f", {"loom": {"goomba"}})
    mom = c.SavedMoment("m", "r", "n", 5, 40.0, True, b"", {1: 0.0}, None, None, scene, fly)
    res = c.RunResult("r", "f", scene, None, "timeout", None, 0.0, 0.0, 0, False)
    c.RunRequest(fly, scene)
    c.ButtonIntent(frozenset({"A"}), frozenset(), 1)
    assert (mario.airborne, obj.side, knob.scale, out.inputs, mom.frame, res.outcome) == \
        (False, "ahead", "linear", {"LC4": 0.5}, 5, "timeout")
