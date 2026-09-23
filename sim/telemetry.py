"""sim/telemetry.py -- accumulates one dict of column -> value per frame and
writes them as a CSV. No dependency on fly/mario/bridge.

Column order is fixed at construction, whatever order a frame assigns its
keys in; the byte-identical golden comparison depends on it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class TelemetryObserver:
    def __init__(self, columns):
        self.columns = tuple(columns)
        self.rows: list[dict] = []

    def new_row(self) -> dict:
        """A fresh row with every column set to None."""
        return {k: None for k in self.columns}

    def record(self, row: dict) -> None:
        self.rows.append(row)

    @property
    def last_row(self) -> dict | None:
        """The previous row, for run_steering.py's frame_skip repeat."""
        return self.rows[-1] if self.rows else None

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=list(self.columns))

    def write(self, path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(path, index=False)
        print(f"wrote {path}")
        return path
