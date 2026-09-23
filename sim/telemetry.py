"""sim/telemetry.py -- REFACTOR_PLAN.md section 5.2/6: "Telemetry becomes
an observer the episode notifies, so adding a recorded field never edits
the loop -- which matters given how often 017-022 turned on adding one."

Generic: no dependency on fly/mario/bridge, just plain Python + pandas.
`TelemetryObserver` doesn't know what a theta or a DNp01 is -- it accepts
whatever dict of column->value the caller hands it each frame and knows
how to accumulate and write those rows out. The COLUMN ORDER is fixed at
construction (matching how `run_steering.py`'s own `log = {k: [] for k in
(...)}` dict comprehension fixed it before this observer existed) --
`to_dataframe()`/`write()` always emit columns in that order regardless of
what order a given frame's dict happened to assign keys in, which is what
makes byte-identical CSV comparison against tests/golden/ possible.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class TelemetryObserver:
    def __init__(self, columns):
        self.columns = tuple(columns)
        self.rows: list[dict] = []

    def new_row(self) -> dict:
        """A fresh row with every column present (defaulting to None) --
        callers fill in each frame's values by key, in whatever order is
        convenient; column order in the final CSV is fixed by `self.columns`,
        not by assignment order."""
        return {k: None for k in self.columns}

    def record(self, row: dict) -> None:
        self.rows.append(row)

    @property
    def last_row(self) -> dict | None:
        """For a caller that needs to repeat the previous frame's values
        (run_steering.py's frame_skip path) without knowing what any of
        them mean."""
        return self.rows[-1] if self.rows else None

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=list(self.columns))

    def write(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)
        print(f"wrote {path}")
        return path
