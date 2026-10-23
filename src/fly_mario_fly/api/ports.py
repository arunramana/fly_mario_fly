"""The runner's moment store and level catalogue, as the API's JSON shapes. Every moment id a client passes in is
looked up here; an unknown one is a KeyError, which the app answers with 404."""
from __future__ import annotations

from fly_mario_fly import runner
from fly_mario_fly.api import convert as V
from fly_mario_fly.api import schemas as S


def level_catalogue(runs_dir=None) -> list:
    """The 32 stages in order, then the whole game, Lost Levels and Random Stages."""
    rank = {lv: i for i, lv in enumerate(V.LEVEL_ORDER)}
    return sorted((V.level_to_dto(lv) for lv in runner.level_catalogue(runs_dir)), key=lambda d: rank.get(d.id, len(rank)))


def level_info(level_id: str, runs_dir=None) -> S.LevelInfo:
    if level_id not in {lv.id for lv in runner.level_catalogue(runs_dir)}:
        raise KeyError(f"no level {level_id!r}")
    return V.level_to_dto(runner.level_info(level_id, runs_dir))


def list_moments(run_id: str) -> list:
    return [V.moment_to_dto(i) for i in runner.list_moments(run_id)]


def get_moment(moment_id: str) -> S.MomentSummary:
    return V.moment_to_dto(runner.moment_info(moment_id))


def rename_moment(moment_id: str, name: str) -> S.MomentSummary:
    return V.moment_to_dto(runner.rename_moment(moment_id, name))


def delete_moment(moment_id: str) -> None:
    runner.delete_moment(moment_id)


def tries_from(moment_id: str) -> list:
    return [S.TryDTO(run_id=t.run_id, change=t.change, outcome=t.outcome, max_x=t.max_x)
            for t in runner.tries_from(moment_id)]
