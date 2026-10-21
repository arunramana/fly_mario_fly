"""Parity with the old code: the 636/656/881/907 matrices equal the old caches exactly (same neuron order), and
the rate model gives identical rates. Needs $FLY_MARIO_DATA (the new brains) and the old tutorials/_cache
(found by walking up from this file, or $FLY_MARIO_OLD_CACHE). Deleted at cleanup."""
import importlib.util
import os
from pathlib import Path

import numpy as np
import pytest

from fly_mario.fly.brain import RateModel, build_brain
from fly_mario.fly.spec import BrainSpec

pd = pytest.importorskip("pandas")

HERE = Path(__file__).resolve()
ROWS = [  # (mechanisms, old W file, old body table, neuron count)
    ((), "W_steer.npy", "steer_bodies.parquet", 636),
    (("hearing",), "W_steer_jo.npy", "steer_jo_bodies.parquet", 656),
    (("hearing", "attraction"), "W_steer_jo_orn.npy", "steer_jo_orn_bodies.parquet", 881),
    (("hearing", "attraction", "aversion"), "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet", 907),
]


def _old_cache() -> Path:
    env = os.environ.get("FLY_MARIO_OLD_CACHE")
    for c in ([Path(env)] if env else []) + [p / "tutorials" / "_cache" for p in HERE.parents]:
        if (c / "W_steer.npy").exists():
            return c
    pytest.skip("old tutorials/_cache not found (set FLY_MARIO_OLD_CACHE)")


def _old_brain_module():
    for p in HERE.parents:
        f = p / "flyrun" / "brain.py"
        if f.exists():
            spec = importlib.util.spec_from_file_location("old_flyrun_brain", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    pytest.skip("old flyrun/brain.py not found")


pytestmark = [pytest.mark.parity_old, pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")]


@pytest.mark.parametrize("mechs,wfile,bfile,n", ROWS, ids=[str(r[3]) for r in ROWS])
def test_matrix_equals_old_cache(mechs, wfile, bfile, n):
    cache = _old_cache()
    new = build_brain(BrainSpec(mechanisms=mechs))
    old_W, old_b = np.load(cache / wfile), pd.read_parquet(cache / bfile)
    assert new.n == n == old_W.shape[0]
    assert np.array_equal(new.body_ids, old_b.bodyId.to_numpy()), "neuron order differs"
    assert (new.types == old_b.type.to_numpy().astype(str)).all()
    assert np.array_equal(new.W, old_W), f"max |dW| = {np.abs(new.W - old_W).max()}"
    assert np.array_equal(new.signs, old_b.sign.to_numpy(float))


def test_group_masks_match_the_old_loader():
    cache = _old_cache()
    old = _old_brain_module()
    os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"] = "W_steer_jo_orn_sour.npy", "steer_jo_orn_sour_bodies.parquet"
    try:
        old_masks = old.load_brain(cache).masks
    finally:
        del os.environ["FLYRUN_WFILE"], os.environ["FLYRUN_BODIES"]
    new = build_brain(BrainSpec(mechanisms=("hearing", "attraction", "aversion")))
    for name, mask in old_masks.items():
        assert np.array_equal(new.masks[name], mask), name


def test_200_steps_of_the_rate_model_identical():
    cache = _old_cache()
    old = _old_brain_module()
    new = build_brain(BrainSpec(mechanisms=("hearing", "attraction", "aversion")))
    W_old = np.load(cache / "W_steer_jo_orn_sour.npy")
    model = RateModel()
    rng = np.random.default_rng(123)                        # the sensor noise, same seed for both
    h_old, h_new = np.zeros(new.n), new.new_state()
    for frame in range(20):                                 # 20 frames x 10 substeps = 200 steps
        I = np.zeros(new.n)
        for name, level in (("LPLC2_R", 0.4 + 0.02 * frame), ("LC4_R", 0.1), ("LC10a_R", 0.5)):
            m = new.masks[name]
            I[m] = level * (1.0 + 0.05 * rng.standard_normal(m.sum()))
        for _ in range(model.substeps):
            h_old = old.step(h_old, W_old, model.g, I, model.alpha, model.clip)
        h_new = new.advance(h_new, I, model)
    assert h_old.max() > 0
    assert np.array_equal(h_old, h_new)
