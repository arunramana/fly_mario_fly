"""scripts/validate_entity_profiles_sweep.py -- follow-up to
scripts/validate_entity_profiles.py (projects/legacy/runs/029_c8a_
validation.md's first section): that run used a SINGLE shuffle_seed=1,
and found its default-profile jump/escape circuit never engaged at all
(0% survival, zero escape-jump spikes, zero variance across 8 seeds) --
a degenerate baseline, not a working-but-different one. This script
answers the question that raised: how common is a non-engaging shuffled
network, and what does the profile's effect look like on the networks
that DO engage?

Design: {real, shuffled seeds 1-8} x {default, modified profile} x 8 run
seeds, sigma=0.05. "Modified" is the same GOOMBA danger_weight=2.0,
intensity=1.4 profile as before. For each of the 8 shuffled networks,
"engages" means at least one escape-jump spike across its 8 default-
profile run seeds; "never engages" means zero. The profile effect
(modified fitness mean - default fitness mean) is then compared: one
value for real (with its own run-seed spread), and a per-network value
for every ENGAGING shuffled network, reported as mean +/- spread across
those networks -- excluding non-engaging ones, since a network that never
escapes can't show an escape/steering tradeoff at all.

No new videos (the original two already cover what a viewer can see).
Appends a new section to projects/legacy/runs/029_c8a_validation.md
rather than rewriting the first one.

    .venv/Scripts/python.exe -m scripts.validate_entity_profiles_sweep
"""
from __future__ import annotations

import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import json

import numpy as np

from scripts.validate_entity_profiles import (
    LEVEL, MAX_FRAMES, RUNS_DIR, SEEDS, SIGMA,
    _cell_stats, _modified_profile, _run,
)

SHUFFLE_SEEDS = list(range(1, 9))  # eight distinct shuffled networks, not just one


def _network_stats(shuffle_seed: int | None, modified) -> dict:
    default_rows = [_run(seed, shuffle_seed, None) for seed in SEEDS]
    modified_rows = [_run(seed, shuffle_seed, modified) for seed in SEEDS]
    default_stats = _cell_stats(default_rows)
    modified_stats = _cell_stats(modified_rows)
    engaged = default_stats["escape_jump_spikes_mean"] > 0.0
    return {
        "shuffle_seed": shuffle_seed,
        "engaged": engaged,
        "default": default_stats,
        "modified": modified_stats,
        "fitness_gap": modified_stats["fitness_mean"] - default_stats["fitness_mean"],
    }


def main() -> None:
    modified = _modified_profile()

    print(f"real ({SEEDS[0]}-{SEEDS[-1]})...")
    real = _network_stats(None, modified)
    print(f"  engaged={real['engaged']} gap={real['fitness_gap']:.1f}")

    shuffled = []
    for shuffle_seed in SHUFFLE_SEEDS:
        print(f"shuffle_seed={shuffle_seed} ({SEEDS[0]}-{SEEDS[-1]})...")
        net = _network_stats(shuffle_seed, modified)
        shuffled.append(net)
        print(f"  engaged={net['engaged']} default_survival={net['default']['survival_rate']:.2f} "
              f"gap={net['fitness_gap']:.1f}")

    n_engaged = sum(n["engaged"] for n in shuffled)
    n_total = len(shuffled)
    fraction_never_engaged = 1.0 - n_engaged / n_total
    print(f"\n{n_total - n_engaged}/{n_total} shuffled networks never engaged their jump circuit "
          f"under the default profile (fraction={fraction_never_engaged:.3f})")

    engaging = [n for n in shuffled if n["engaged"]]
    engaging_gaps = [n["fitness_gap"] for n in engaging]
    gap_mean = float(np.mean(engaging_gaps)) if engaging_gaps else float("nan")
    gap_std = float(np.std(engaging_gaps)) if engaging_gaps else float("nan")
    print(f"\nprofile effect (modified - default fitness), real: {real['fitness_gap']:.1f} "
          f"(within-network seed std: default={real['default']['fitness_std']:.1f}, "
          f"modified={real['modified']['fitness_std']:.1f})")
    print(f"profile effect, engaging shuffled networks (n={len(engaging)}): "
          f"mean={gap_mean:.1f} std-across-networks={gap_std:.1f}")

    number_path = RUNS_DIR / "029_c8a_validation_sweep.json"
    number_path.write_text(json.dumps({
        "config": {"level": LEVEL, "max_frames": MAX_FRAMES, "sigma": SIGMA, "seeds": SEEDS,
                   "shuffle_seeds": SHUFFLE_SEEDS,
                   "modified_profile": {"GOOMBA": {"danger_weight": 2.0, "intensity": 1.4}}},
        "real": real,
        "shuffled": shuffled,
        "n_engaged": n_engaged,
        "n_total": n_total,
        "fraction_never_engaged": fraction_never_engaged,
        "engaging_profile_effect_mean": gap_mean,
        "engaging_profile_effect_std": gap_std,
    }, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwrote {number_path}")

    _append_note(real, shuffled, n_engaged, n_total, fraction_never_engaged, gap_mean, gap_std)


def _append_note(real, shuffled, n_engaged, n_total, fraction_never_engaged, gap_mean, gap_std) -> None:
    engaging = [n for n in shuffled if n["engaged"]]
    non_engaging = [n for n in shuffled if not n["engaged"]]

    per_network_rows = "\n".join(
        f"| {n['shuffle_seed']} | {'yes' if n['engaged'] else '**no**'} | "
        f"{n['default']['survival_rate']*100:.0f}% | {n['default']['fitness_mean']:.1f} | "
        f"{n['modified']['fitness_mean']:.1f} | {n['fitness_gap']:.1f} |"
        for n in shuffled
    )

    close = abs(real["fitness_gap"] - gap_mean) < 0.25 * max(abs(real["fitness_gap"]), abs(gap_mean), 1e-9) \
        if engaging else None
    if not engaging:
        verdict = (
            "Every one of the 8 shuffled networks tested was non-engaging under "
            "the default profile -- no engaging-network comparison is possible "
            "with this sample. shuffle_seed=1's earlier finding wasn't a fluke "
            "of one draw; it looks like the common case for this circuit/level/"
            "frame-count combination, not the exception."
        )
    elif close:
        verdict = (
            f"Restricted to networks whose jump circuit actually engages, the "
            f"prediction holds much better: the profile's effect on engaging "
            f"shuffled networks (mean {gap_mean:.1f}, std {gap_std:.1f} across "
            f"{len(engaging)} networks) is close to the real connectome's own "
            f"effect ({real['fitness_gap']:.1f}). The original 029 finding's "
            f"apparent contradiction of the gains-only prediction was almost "
            f"entirely explained by including a non-engaging network in the "
            f"comparison, not by a genuine connectome-gain interaction."
        )
    else:
        verdict = (
            f"Even restricted to engaging networks, the profile's effect "
            f"(mean {gap_mean:.1f}, std {gap_std:.1f} across {len(engaging)} "
            f"networks) still differs substantially from the real connectome's "
            f"own effect ({real['fitness_gap']:.1f}). Excluding non-engaging "
            f"networks narrows the gap-mismatch from the original 029 finding "
            f"but doesn't fully explain it -- there may be a genuine, milder "
            f"interaction between the connectome's structure and the per-kind "
            f"gain worth its own follow-up."
        )

    note = (
        f"\n---\n\n"
        f"## 029, follow-up -- sweeping 8 shuffled networks instead of 1\n\n"
        f"**Setup.** Same design as the section above, but "
        f"`{{real, shuffled shuffle_seed=1..8}} x {{default, modified profile}}`, "
        f"still {len(SEEDS)} run seeds per cell, level {LEVEL}, {MAX_FRAMES} "
        f"frames, sigma={SIGMA}, same modified profile (GOOMBA "
        f"danger_weight=2.0, intensity=1.4). Answers the question the first "
        f"section's finding raised: was `shuffle_seed=1`'s non-engaging jump "
        f"circuit a one-off draw, or the common case? No new videos -- the "
        f"original two already show what a viewer can see. Full per-network "
        f"stats in `029_c8a_validation_sweep.json`.\n\n"
        f"**\"Never engages\" defined.** Under the default profile, zero "
        f"escape-jump spikes across all {len(SEEDS)} run seeds for that "
        f"network (the same signature `shuffle_seed=1` showed originally: "
        f"0% survival, 0 spikes, 0 variance).\n\n"
        f"**What happened.**\n\n"
        f"**{n_total - n_engaged}/{n_total} shuffled networks never engaged "
        f"their jump circuit under the default profile "
        f"(fraction={fraction_never_engaged:.2f}).**\n\n"
        f"| shuffle_seed | engages? | default survival | default fitness | "
        f"modified fitness | (modified-default) gap |\n"
        f"|---|---|---|---|---|---|\n"
        f"{per_network_rows}\n\n"
        f"Profile effect (modified - default fitness):\n\n"
        f"- real: {real['fitness_gap']:.1f} (within-network seed std: "
        f"default={real['default']['fitness_std']:.1f}, "
        f"modified={real['modified']['fitness_std']:.1f})\n"
        f"- engaging shuffled networks ({len(engaging)}/{n_total}): "
        f"mean={gap_mean:.1f}, std-across-networks={gap_std:.1f}\n\n"
        f"**What we learned.** {verdict}\n"
    )
    path = RUNS_DIR / "029_c8a_validation.md"
    with path.open("a", encoding="utf-8") as f:
        f.write(note)
    print(f"appended a new section to {path}")


if __name__ == "__main__":
    main()
