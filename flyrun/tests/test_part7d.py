"""Part 7d: the search engine logs, checkpoints, resumes, and treats a constraint failure as fitness -inf."""
import copy
import math
import multiprocessing as mp
from pathlib import Path

import pandas as pd

from flyrun import part7, search7

CFG = Path(__file__).resolve().parent.parent / "configs" / "part7.yaml"


def _tiny():
    cfg = part7.load_config(CFG)
    cfg["cmaes"]["popsize"] = 4
    cfg["episodes"]["train"] = cfg["episodes"]["train"][:1]
    return cfg


def test_run_restart_logs_resumes_and_flags_infeasible(tmp_path):
    cfg, hdr = _tiny(), "# test"
    r = next(r for r in cfg["restarts"] if r["label"] == "warm_r3")
    st = dict(git_commit="x")
    with mp.get_context("spawn").Pool(4, initializer=part7._init) as pool:
        s1 = search7.run_restart(pool, cfg, r, tmp_path / "a", 1, st, hdr, log=lambda *a, **k: None)
        assert s1["gen"] == 1 and s1["done"]
        # r3's start genome is feasible on its own TRAIN episode 0 (7a check: all constraints ok)
        assert s1["best"] is not None and math.isfinite(s1["best"]["fitness"])
        ev = pd.read_csv(tmp_path / "a" / "all_evals.csv", comment="#")
        assert len(ev) == 4 and ev.iloc[0].feasible and ev.iloc[0].gen == 0
        # resume: a finished restart is returned untouched; extending the budget continues from the checkpoint
        s1["done"] = False
        search7._save(tmp_path / "a" / "state.pkl", s1)
        s2 = search7.run_restart(pool, cfg, r, tmp_path / "a", 2, st, hdr, log=lambda *a, **k: None)
        assert s2["gen"] == 2
        assert list(pd.read_csv(tmp_path / "a" / "gen.csv", comment="#").gen) == [0, 1]
        # a constraint no genome can meet: every genome is -inf, nothing is selected as "best", nothing crashes
        bad = copy.deepcopy(cfg)
        bad["constraints"]["max_blind_presses"] = -1
        s3 = search7.run_restart(pool, bad, r, tmp_path / "b", 1, st, hdr, log=lambda *a, **k: None)
        assert s3["best"] is None
        ev = pd.read_csv(tmp_path / "b" / "all_evals.csv", comment="#")
        assert (~ev.feasible).all() and (ev.fitness == float("-inf")).all() and ev.fail.str.contains("blind").all()
