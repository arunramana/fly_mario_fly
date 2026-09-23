# What this file does, in plain English:
# Checks the per-frame log recorder (sim/telemetry.py) on its own: new rows
# start with every column empty, column order stays fixed whatever order
# values are filled in, the previous row can be copied to repeat a frame,
# saving creates missing folders, and adding a column needs no change to
# the recorder itself.
"""
sim.telemetry.TelemetryObserver in isolation.
"""
from __future__ import annotations

from sim.telemetry import TelemetryObserver

COLUMNS = ("frame", "mario_x", "theta")


def test_new_row_has_every_column_present():
    obs = TelemetryObserver(COLUMNS)
    row = obs.new_row()
    assert set(row) == set(COLUMNS)
    assert all(v is None for v in row.values())


def test_record_and_to_dataframe_preserve_column_order():
    obs = TelemetryObserver(COLUMNS)
    row = obs.new_row()
    row["theta"] = 0.5
    row["frame"] = 0
    row["mario_x"] = 40
    obs.record(row)
    df = obs.to_dataframe()
    assert list(df.columns) == list(COLUMNS)
    assert df.iloc[0]["frame"] == 0 and df.iloc[0]["mario_x"] == 40 and df.iloc[0]["theta"] == 0.5


def test_last_row_supports_the_frame_skip_repeat_pattern():
    obs = TelemetryObserver(COLUMNS)
    assert obs.last_row is None
    row = obs.new_row()
    row["frame"], row["mario_x"], row["theta"] = 0, 40, 0.5
    obs.record(row)

    repeated = dict(obs.last_row)
    repeated["frame"] = 1
    repeated["mario_x"] = 41
    obs.record(repeated)

    df = obs.to_dataframe()
    assert df.iloc[1]["theta"] == 0.5  # carried over, unchanged
    assert df.iloc[1]["frame"] == 1 and df.iloc[1]["mario_x"] == 41


def test_write_creates_parent_dirs_and_matches_dataframe(tmp_path):
    obs = TelemetryObserver(COLUMNS)
    row = obs.new_row()
    row["frame"], row["mario_x"], row["theta"] = 0, 40, 0.5
    obs.record(row)
    out = tmp_path / "nested" / "telemetry.csv"
    obs.write(out)
    assert out.exists()
    import pandas as pd
    on_disk = pd.read_csv(out)
    assert list(on_disk.columns) == list(COLUMNS)


def test_adding_a_new_field_touches_only_the_row_dict_and_columns_tuple():
    """The whole point of the observer: a caller adds a field by adding it
    to the columns tuple and setting it in its own row dict -- nothing in
    THIS class needs to change."""
    columns = COLUMNS + ("new_field",)
    obs = TelemetryObserver(columns)
    row = obs.new_row()
    row["frame"], row["mario_x"], row["theta"], row["new_field"] = 0, 40, 0.5, "hi"
    obs.record(row)
    assert list(obs.to_dataframe().columns) == list(columns)
