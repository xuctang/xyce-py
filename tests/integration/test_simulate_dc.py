from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_simulate_dc_voltage_source_sweep_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 0.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Resistor("r2", 1000)])

    translated = circuit.simulate_dc("V_src", "0", "10", "1").translated_waveforms()

    assert len(translated) == 11
    assert "V(vout)" in translated.columns


def test_simulate_dc_returns_expected_row_count_and_endpoints(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 0.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Resistor("r2", 1000)])

    translated = circuit.simulate_dc("V_src", "0", "10", "1").translated_waveforms()

    assert translated["V(vout)"].iloc[0] == pytest.approx(0.0, abs=1e-3)
    assert translated["V(vout)"].iloc[-1] == pytest.approx(5.0, abs=1e-2)
