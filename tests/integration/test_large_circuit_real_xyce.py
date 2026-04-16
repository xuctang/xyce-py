from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_large_resistive_ladder_real_xyce_produces_structurally_valid_output(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])

    previous_node = "vin"
    for index in range(1, 11):
        node_id = f"n{index}"
        circuit.add_branch(previous_node, node_id, [Resistor(f"series_r{index}", 1000 + index * 100)])
        circuit.add_branch(node_id, "gnd", [Resistor(f"shunt_r{index}", 2200 + index * 100)])
        previous_node = node_id

    translated = circuit.simulate_op().translated_waveforms()
    voltage_columns = [column for column in translated.columns if column.startswith("V(")]
    row = translated.iloc[0][voltage_columns]

    assert len(translated) == 1
    assert len(voltage_columns) == 11
    assert row.notna().all()
    assert all(0.0 <= value <= 10.0 for value in row)
