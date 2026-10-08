# What this file does, in plain English:
# Tests the E1d scene distribution (docs/SPEC_e1_scene_dist.md): the scene drawn for a seed is
# repeatable, stays inside the ranges written down before any run, does not share the brain's
# noise stream, always passes the scene check (Goomba on screen and ahead, Mario standing
# still), and the default fixed E1 scene is untouched. Nothing here checks whether the fly wins.
from __future__ import annotations

import dataclasses

import numpy as np

from brain import e1, scenes

SEEDS = list(range(3800, 3850))


def test_draw_is_deterministic_per_seed_and_in_the_preregistered_ranges():
    for s in SEEDS:
        d = scenes.draw_scene_params(s)
        assert d == scenes.draw_scene_params(s)
        assert 50 <= d["walk_frames"] <= 65 and 40 <= d["settle_frames"] <= 70
    # the fixed ranges are the ones in the spec
    assert (scenes.E1D_WALK_MIN, scenes.E1D_WALK_MAX, scenes.E1D_SETTLE_MIN, scenes.E1D_SETTLE_MAX) == (50, 65, 40, 70)
    assert len({tuple(scenes.draw_scene_params(s).values()) for s in SEEDS}) > 25      # many different scenes in 50 seeds


def test_draw_covers_both_range_ends_over_many_seeds():
    ds = [scenes.draw_scene_params(s) for s in range(2000)]
    assert {d["walk_frames"] for d in ds} == set(range(50, 66)) and {d["settle_frames"] for d in ds} == set(range(40, 71))


def test_scene_stream_is_independent_of_the_brain_noise_stream():
    before = [scenes.draw_scene_params(s) for s in SEEDS[:10]]
    np.random.seed(0)
    np.random.default_rng(3800).standard_normal(1000)           # consuming the brain-style stream changes nothing
    assert before == [scenes.draw_scene_params(s) for s in SEEDS[:10]]
    brain_like = [int(np.random.default_rng(s).integers(50, 66)) for s in SEEDS]
    assert brain_like != [scenes.draw_scene_params(s)["walk_frames"] for s in SEEDS]      # a different stream, not the seed's own


def test_drawn_scene_spec_carries_the_draw_and_the_same_buttons():
    base, spec = scenes.load_scene(), scenes.draw_scene(3801)
    d = scenes.draw_scene_params(3801)
    assert spec.draw == d and spec.to_dict()["draw"] == d and spec.id == scenes.E1D_SCENE_ID
    assert [b for b, _ in spec.log] == [b for b, _ in base.log] and [n for _, n in spec.log] == [d["walk_frames"], d["settle_frames"]]
    assert spec.hash() != base.hash() and spec.hash() == scenes.draw_scene(3801).hash()


def test_check_scene_passes_for_50_draws():
    from mario.emulator.env import make_env
    env = make_env("1-1")
    for s in SEEDS:
        scenes.build_scene(env, scenes.draw_scene(s))
        c = scenes.check_scene(env.unwrapped.ram)
        assert scenes.scene_ok(c), (s, c)
        assert c["goomba_dx_px"] >= 3 * e1.SPRITE_PX
    env.close()


def test_default_e1_scene_and_result_are_unchanged():
    spec = scenes.load_scene()
    assert spec.draw is None and set(spec.to_dict()) == {"id", "level", "log_frames", "scene_hash"}
    assert spec.id == scenes.E1_SCENE_ID and spec.n_frames == 110
    assert "scene_draw" not in {f.name for f in dataclasses.fields(e1.E1Result)}
    assert [f.name for f in dataclasses.fields(e1.E1dResult)][-2:] == ["scene_draw", "a_trace"]
    assert scenes.draw_scene(3800).log != spec.log or scenes.draw_scene_params(3800) == {"walk_frames": 60, "settle_frames": 50}
