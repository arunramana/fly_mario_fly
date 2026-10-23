"""evolve: elitism, resume and determinism of the search loop, with the (slow) emulator replaced by a fake fitness."""
import json

import numpy as np
import pytest

from fly_mario_fly.evolve import search


class FakePool:
    """Stands in for the episode pool: fitness is a smooth function of the knobs, so no emulator is needed."""

    def __init__(self):
        self.calls = 0

    def map(self, jobs):
        self.calls += 1
        out = []
        for j in jobs:
            x = sum(np.log1p(abs(v)) for v in j["fly"].knobs.values())
            out.append({"max_x": 100.0, "score": 0.0, "outcome": "timeout", "violations": 0, "frames": 10,
                        "fitness": float(np.sin(x)), "hash": ""})
        return out

    def close(self):
        pass


@pytest.fixture
def patched(tmp_path, monkeypatch):
    monkeypatch.setenv("FLY_MARIO_FLY_DATA", str(tmp_path))
    monkeypatch.setattr(search, "_keep_run", lambda *a, **k: "run")
    return tmp_path


def cfg(gens, seed=3):
    return {"id": f"evo_t{seed}", "fly": "champion_e1s", "level": "1-1", "gens": gens, "seed": seed, "pop": 6,
            "workers": 0, "moments": [], "train_n": 2, "flag_x": 3161.0}


def test_best_ever_never_below_start_and_never_decreases(patched):
    out = search.run(cfg(4), pool=FakePool(), log=lambda s: None)
    rows = out["rows"]
    be = [r["best_ever"] for r in rows]
    assert be == sorted(be) and be[-1] >= rows[0]["best"]          # row -1 is the start
    assert out["best"]["fitness"] == be[-1]


def test_same_seed_same_result(patched):
    a = search.run(cfg(3), pool=FakePool(), log=lambda s: None)
    b = search.run({**cfg(3), "id": "evo_other"}, pool=FakePool(), log=lambda s: None)
    assert [r["best"] for r in a["rows"]] == [r["best"] for r in b["rows"]]
    assert a["best"]["values"] == b["best"]["values"]


def test_resume_equals_uninterrupted(patched):
    whole = search.run({**cfg(4), "id": "evo_whole"}, pool=FakePool(), log=lambda s: None)
    search.run({**cfg(2), "id": "evo_part"}, pool=FakePool(), log=lambda s: None)
    resumed = search.run({**cfg(4), "id": "evo_part"}, pool=FakePool(), log=lambda s: None)
    assert [r["best"] for r in resumed["rows"]] == [r["best"] for r in whole["rows"]]


def test_best_yaml_carries_provenance(patched):
    out = search.run(cfg(2), pool=FakePool(), log=lambda s: None)
    import yaml
    d = yaml.safe_load((patched / "runs" / "evo_t3" / "best.yaml").read_text())
    assert d["provenance"]["evolved_from"] == "champion_e1s" and d["provenance"]["seed"] == 3
    assert "generation" in d["provenance"]
    assert json.loads((patched / "runs" / "evo_t3" / "progress.json").read_text())["rows"]
