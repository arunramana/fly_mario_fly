"""Golden: the 636/656/881/907 matrices equal what the old code cached (hash of W, same neuron order, same types and
signs, same group masks), and 200 steps of the rate model give the old rate vector. Needs $FLY_MARIO_DATA."""
import hashlib
import os

import numpy as np
import pytest

from fly_mario.fly.brain import RateModel, build_brain
from fly_mario.fly.spec import BrainSpec
from golden_data import GOLDEN

pytestmark = pytest.mark.skipif(not os.environ.get("FLY_MARIO_DATA"), reason="FLY_MARIO_DATA not set")
SIZES = ["636", "656", "881", "907"]
SOUR = ("hearing", "attraction", "aversion")


def sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


@pytest.mark.parametrize("n", SIZES)
def test_matrix_and_neuron_order_equal_the_frozen_old_brain(golden, n):
    row = golden("brains.json")[n]
    new = build_brain(BrainSpec(mechanisms=tuple(row["mechanisms"])))
    assert new.n == row["n"] == int(n)
    assert new.body_ids.tolist() == row["body_ids"], "neuron order differs"
    assert sha(new.types.astype("U40")) == row["types_sha256"]
    assert sha(new.signs.astype(float)) == row["signs_sha256"]
    assert sha(new.W.astype(np.float64)) == row["W_sha256"], "W differs from the old cache"


def test_group_masks_equal_the_frozen_old_loader(golden):
    row = golden("brains.json")["907"]
    new = build_brain(BrainSpec(mechanisms=SOUR))
    assert set(new.masks) >= set(row["masks"])
    for name, want in row["masks"].items():
        m = new.masks[name]
        assert (int(m.sum()), sha(np.flatnonzero(m).astype(np.int64))) == (want["count"], want["sha256"]), name


def test_200_steps_of_the_rate_model_equal_the_frozen_old_rates():
    new = build_brain(BrainSpec(mechanisms=SOUR))
    model, rng = RateModel(), np.random.default_rng(123)            # the sensor noise, same seed as when it was frozen
    h = new.new_state()
    for frame in range(20):                                         # 20 frames x 10 substeps = 200 steps
        I = np.zeros(new.n)
        for name, level in (("LPLC2_R", 0.4 + 0.02 * frame), ("LC4_R", 0.1), ("LC10a_R", 0.5)):
            m = new.masks[name]
            I[m] = level * (1.0 + 0.05 * rng.standard_normal(m.sum()))
        h = new.advance(h, I, model)
    want = np.load(GOLDEN / "brains_rate.npz")["h"]
    assert want.max() > 0
    # sparse W (CSR) sums in another order than the dense product the answer was frozen with: last bits only
    assert np.allclose(h, want, rtol=0, atol=1e-12)
