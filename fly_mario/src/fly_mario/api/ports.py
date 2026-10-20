"""Things the API needs that the runner does not provide yet. Each is a stub that raises NotImplementedError (the
app answers 501); together they are the list for the next runner step.

  list_moments / get_moment   a store of SavedMoments per run (Run.snapshot() and Run.restore() exist; nothing keeps
                              the moments, nothing lists them, and no cadence takes automatic ones)
  resume                      start a Run from a moment id (RunRequest.from_moment): Run has no from_moment argument
                              and no way to look a moment up
  frame_objects               the ObjectInstances found in a frame (Run keeps them in a private attribute)
  scroll_x                    the screen's scroll offset, to put level-pixel overlays on the 256-px picture
  level_catalogue             level width, the object types each level holds, cleared/locked status

level_catalogue has a fallback so the level grid is not empty: the 32 stages, all open, width and objects unknown.
"""
from __future__ import annotations


def _lacks(what: str):
    raise NotImplementedError(f"the runner has no {what} yet")


def list_moments(run_id: str) -> list:
    _lacks("saved-moment store")


def get_moment(moment_id: str):
    _lacks("saved-moment store")


def resume(run, moment_id: str) -> None:
    _lacks("resume-from-moment")


def frame_objects(run) -> list:
    _lacks("per-frame object list")


def scroll_x(run) -> int:
    _lacks("scroll offset")


def level_catalogue() -> list:
    """[{id, label, kind, status, width, objects}] for every level."""
    out = []
    for world in range(1, 9):
        for stage in range(1, 5):
            out.append({"id": f"{world}-{stage}", "label": f"{world}-{stage}",
                        "kind": "castle" if stage == 4 else "stage", "status": "open", "width": None, "objects": []})
    return out
