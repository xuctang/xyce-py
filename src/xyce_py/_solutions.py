from __future__ import annotations

from collections.abc import Hashable, Mapping

import pandas as pd


def validate_solution_row(row: object, waveforms: pd.DataFrame) -> int:
    if isinstance(row, bool) or not isinstance(row, int):
        raise TypeError("row must be an integer.")
    if row < 0 or row >= len(waveforms):
        raise IndexError("row is out of range for waveforms.")
    return row


def node_voltage_updates_from_waveforms(
    waveforms: pd.DataFrame,
    spice_to_user_node: Mapping[str, Hashable],
    row: object,
) -> dict[Hashable, object]:
    row = validate_solution_row(row, waveforms)
    node_voltage_updates: dict[Hashable, object] = {}
    solution_row = waveforms.iloc[row]
    for column, value in solution_row.items():
        if not (isinstance(column, str) and column.startswith("V(") and column.endswith(")")):
            continue
        spice_id = column[2:-1]
        if spice_id == "0" or spice_id not in spice_to_user_node:
            continue
        node_voltage_updates[spice_to_user_node[spice_id]] = value
    return node_voltage_updates
