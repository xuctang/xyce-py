from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_simulate_ac_rc_low_pass_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 1.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Capacitor("c1", "1u")])

    result = circuit.simulate_ac("DEC", "10", "1", "1e6")

    assert len(result.waveforms) > 1
    assert any(column.upper().startswith("FREQ") for column in result.waveforms.columns)


def test_simulate_ac_returns_frequency_and_requested_voltage_columns(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 1.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Capacitor("c1", "1u")])

    result = circuit.simulate_ac("DEC", "5", "1", "1e3", print_vars=["V(N_2)"])

    assert any(column.upper().startswith("FREQ") for column in result.waveforms.columns)
    assert any("N_2" in column.upper() for column in result.waveforms.columns)
