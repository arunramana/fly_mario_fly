"""scripts/validate_entity_profiles.py -- docs/SPEC_entity_perception.md
section 5's validation batch for C8a: {real, shuffled} x {default,
modified profile}, 8 seeds per cell, sigma=0.05 (inside NoiseParams.sigma's
own measured range). "Modified" is GOOMBA danger_weight=2.0,
intensity=1.4 (the same profile docs/SPEC_entity_perception.md section 3
and tests/test_c8a_entity_profiles.py already use).

Prediction, stated before running anything (SPEC section 5): C8a is a
gains-only change -- no new wiring, the same DNa01/DNa02/LC4/LPLC2
populations as today just driven by different numbers. A gains-only
change shouldn't give the network anything new to discriminate WITH, so
the (modified - default) gap should be about the same size under the real
connectome and the shuffled one. If the real-vs-shuffled gap in "how much
the profile mattered" turns out to be large, that's the surprising
result, not predicted by this design, and worth its own follow-up.

Also renders the two required videos, same seed (seed 0), both under the
modified profile: one real-connectome, one shuffled -- the condition
where a viewer can actually see something different from a stock run.

    .venv/Scripts/python.exe -m scripts.validate_entity_profiles
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import json
from pathlib import Path

import numpy as np

import re

import run_steering
from bridge.entity_profiles import EntityProfiles, KindProfile, OdourChannel, load as load_profiles
from mario.entities.kinds import EntityKind
from sim.fitness import FitnessWeights, compute_fitness

PROJECT_NAME = "legacy"
LEVEL = "1-1"
MAX_FRAMES = 600
SIGMA = 0.05
SEEDS = list(range(8))
SHUFFLE_SEED_FOR_SHUFFLED = 1  # one fixed shuffled network, same convention as tests/test_c5_shuffle.py

PROJECT_ROOT = Path(__file__).parent.parent / "projects" / PROJECT_NAME
RUNS_DIR = PROJECT_ROOT / "runs"


def _next_run_number() -> int:
    """Scans RUNS_DIR's own filenames for the highest NNN prefix --
    deliberately NOT tool.core.run_store.next_run_number, which reads
    projects/<name>/tool_runs/index.json, a SEPARATE numbering lineage
    the GUI's Play button maintains for itself. This script runs outside
    the GUI/tool pipeline entirely (calls run_steering.main() directly),
    so it continues the human-maintained docs/RUNS.md numbering visible
    in this directory's own filenames instead -- using the tool's index
    picked "002" here once, silently colliding with nothing but also not
    continuing from 028, the actual latest file on disk."""
    numbers = [int(m.group(1)) for p in RUNS_DIR.glob("*")
               if (m := re.match(r"^(\d{3})", p.name))]
    return max(numbers, default=0) + 1


def _modified_profile() -> EntityProfiles:
    default = load_profiles(project_root=None)
    goomba = default.get(EntityKind.GOOMBA)
    boosted = KindProfile(
        odours=tuple(
            OdourChannel(o.channel, o.sign, o.hunger_gated, intensity=1.4) for o in goomba.odours
        ),
        looming_salience=goomba.looming_salience,
        danger_weight=2.0,
        is_food=goomba.is_food,
        body_scale=goomba.body_scale,
    )
    return EntityProfiles(by_kind={**default.by_kind, EntityKind.GOOMBA: boosted})


def _run(seed: int, shuffle_seed: int | None, entity_profiles: EntityProfiles | None,
         out_mp4: str | None = None, record_video: bool = False) -> dict:
    tel, info = run_steering.main(
        out_mp4=out_mp4 or f"/tmp/validate_entity_profiles_{seed}_{shuffle_seed}.mp4",
        level=LEVEL, max_frames=MAX_FRAMES, sigma=SIGMA, seed=seed,
        record_video=record_video, write_telemetry=False,
        shuffle_seed=shuffle_seed, entity_profiles=entity_profiles,
    )
    fitness = compute_fitness(FitnessWeights(), distance=info["max_x_abs"],
                               time=info["n_frames"], points=info.get("score", 0.0))
    return {
        "died_or_flagged": bool(info["died_or_flagged"]),
        "max_x_abs": float(info["max_x_abs"]),
        "fitness": float(fitness),
        "odour_avoids": int(tel["avoid_odor"].sum()),
        "escape_jump_spikes": int(tel["spike"].sum()),
    }


def _cell_stats(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "survival_rate": 1.0 - sum(r["died_or_flagged"] for r in rows) / len(rows),
        "max_x_abs_mean": float(np.mean([r["max_x_abs"] for r in rows])),
        "max_x_abs_std": float(np.std([r["max_x_abs"] for r in rows])),
        "fitness_mean": float(np.mean([r["fitness"] for r in rows])),
        "fitness_std": float(np.std([r["fitness"] for r in rows])),
        "odour_avoids_mean": float(np.mean([r["odour_avoids"] for r in rows])),
        "escape_jump_spikes_mean": float(np.mean([r["escape_jump_spikes"] for r in rows])),
    }


def main() -> None:
    modified = _modified_profile()
    cells: dict[str, dict] = {}

    for connectome_name, shuffle_seed in (("real", None), ("shuffled", SHUFFLE_SEED_FOR_SHUFFLED)):
        for profile_name, profile in (("default", None), ("modified", modified)):
            rows = [_run(seed, shuffle_seed, profile) for seed in SEEDS]
            cells[f"{connectome_name}_{profile_name}"] = _cell_stats(rows)
            print(f"{connectome_name:8s} {profile_name:8s} " +
                  " ".join(f"{k}={v:.3f}" for k, v in cells[f"{connectome_name}_{profile_name}"].items()
                           if isinstance(v, float)))

    gap_real = cells["real_modified"]["fitness_mean"] - cells["real_default"]["fitness_mean"]
    gap_shuffled = cells["shuffled_modified"]["fitness_mean"] - cells["shuffled_default"]["fitness_mean"]
    print(f"\nfitness gap (modified - default): real={gap_real:.3f} shuffled={gap_shuffled:.3f}")
    print(f"prediction (SPEC section 5): the two gaps should be close to each other")

    number = _next_run_number()
    slug_a = f"{number:03d}a_c8a_validation_real"
    slug_b = f"{number:03d}b_c8a_validation_shuffled"
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    _run(0, None, modified, out_mp4=str(RUNS_DIR / f"{slug_a}.mp4"), record_video=True)
    _run(0, SHUFFLE_SEED_FOR_SHUFFLED, modified, out_mp4=str(RUNS_DIR / f"{slug_b}.mp4"), record_video=True)

    results_path = RUNS_DIR / f"{number:03d}_c8a_validation_batch.json"
    results_path.write_text(json.dumps({
        "config": {"level": LEVEL, "max_frames": MAX_FRAMES, "sigma": SIGMA, "seeds": SEEDS,
                   "shuffle_seed_for_shuffled": SHUFFLE_SEED_FOR_SHUFFLED,
                   "modified_profile": {"GOOMBA": {"danger_weight": 2.0, "intensity": 1.4}}},
        "cells": cells,
        "fitness_gap_real": gap_real,
        "fitness_gap_shuffled": gap_shuffled,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {results_path}")

    _write_note(number, slug_a, slug_b, cells, gap_real, gap_shuffled)


def _write_note(number, slug_a, slug_b, cells, gap_real, gap_shuffled) -> None:
    """One shared note for the whole comparison, matching this project's
    own convention (projects/legacy/runs/004_compare.md,
    025_noise.md -- one .md per NUMBERED comparison, not one per
    lettered video)."""
    close = abs(gap_real - gap_shuffled) < 0.25 * max(abs(gap_real), abs(gap_shuffled), 1e-9)
    degenerate = [
        name for name, cell in cells.items()
        if cell["survival_rate"] == 0.0 and cell["escape_jump_spikes_mean"] == 0.0
    ]
    if not close and degenerate:
        verdict = (
            f"The prediction did NOT hold. At least one cell "
            f"({', '.join(degenerate)}) looks DEGENERATE, not just "
            f"different: 0% survival with zero escape-jump spikes across "
            f"every seed is a circuit that never engages its escape "
            f"response at all, not a working-but-worse one. Check "
            f"whether the comparison's baselines are actually comparable "
            f"before concluding the connectome interacts with the gain "
            f"non-linearly -- a degenerate baseline in one cell alone can "
            f"produce an apparent gap mismatch that has nothing to do "
            f"with C8a's own design."
        )
    elif close:
        verdict = (
            "The prediction held: the two gaps are close, consistent with "
            "C8a being a gains-only change that doesn't give the "
            "connectome's wiring anything new to discriminate with."
        )
    else:
        verdict = (
            "The prediction did NOT hold: the real and shuffled gaps "
            "differ more than expected for a gains-only change, and no "
            "cell looks degenerate on its own -- this may be a genuine "
            "non-linear interaction with the connectome's structure, "
            "worth its own follow-up."
        )
    table_rows = "\n".join(
        f"| {name.replace('_', ' / ')} | {cell['fitness_mean']:.1f} (std {cell['fitness_std']:.1f}) | "
        f"{cell['survival_rate']*100:.0f}% | {cell['escape_jump_spikes_mean']:.1f} | "
        f"{cell['odour_avoids_mean']:.1f} |"
        for name, cell in cells.items()
    )
    note = (
        f"# {number:03d} -- C8a validation: real vs. shuffled, default vs. "
        f"modified profile (`{slug_a}.mp4`, `{slug_b}.mp4`)\n\n"
        f"**Setup.** docs/SPEC_entity_perception.md section 5's 2x2 batch: "
        f"{{real, shuffled (shuffle_seed={SHUFFLE_SEED_FOR_SHUFFLED})}} x "
        f"{{default profile, modified profile}}, {len(SEEDS)} seeds "
        f"({SEEDS[0]}-{SEEDS[-1]}) per cell, level {LEVEL}, {MAX_FRAMES} "
        f"frames, sigma={SIGMA}. Modified profile: GOOMBA "
        f"danger_weight=2.0, intensity=1.4 (SPEC section 3's own example). "
        f"Both videos are under the modified profile at seed 0 -- the "
        f"condition where a viewer can see something different from a "
        f"stock run. Full per-cell stats in "
        f"{number:03d}_c8a_validation_batch.json.\n\n"
        f"**Prediction, stated before running anything (SPEC section 5).** "
        f"C8a is a gains-only change -- no new wiring, so the (modified - "
        f"default) fitness gap was predicted to be about the same size "
        f"under the real connectome and the shuffled one.\n\n"
        f"**What happened.**\n\n"
        f"| cell | fitness | survival | escape jumps | odour avoids |\n"
        f"|---|---|---|---|---|\n"
        f"{table_rows}\n\n"
        f"(modified - default) fitness gap: real={gap_real:.1f}, "
        f"shuffled={gap_shuffled:.1f}.\n\n"
        f"**What we learned.** {verdict}\n"
    )
    (RUNS_DIR / f"{number:03d}_c8a_validation.md").write_text(note, encoding="utf-8")
    print(f"wrote {RUNS_DIR / f'{number:03d}_c8a_validation.md'}")


if __name__ == "__main__":
    main()
