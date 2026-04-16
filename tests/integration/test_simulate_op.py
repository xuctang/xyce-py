from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import CurrentSource, Diode, Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_simulate_op_voltage_divider_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Resistor("r2", 1000)])

    result = circuit.simulate_op()
    translated = result.translated_waveforms()

    assert len(result.waveforms) == 1
    assert translated.iloc[0]["V(vin)"] == pytest.approx(10.0, abs=1e-4)
    assert translated.iloc[0]["V(vout)"] == pytest.approx(5.0, abs=1e-2)


def test_simulate_op_three_node_resistor_network_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 12.0)])
    circuit.add_branch("vin", "n1", [Resistor("r1", 1000)])
    circuit.add_branch("n1", "n2", [Resistor("r2", 1000)])
    circuit.add_branch("n2", "gnd", [Resistor("r3", 1000)])

    translated = circuit.simulate_op().translated_waveforms()

    assert translated.iloc[0]["V(vin)"] == pytest.approx(12.0, abs=1e-4)
    assert translated.iloc[0]["V(n1)"] == pytest.approx(8.0, abs=1e-2)
    assert translated.iloc[0]["V(n2)"] == pytest.approx(4.0, abs=1e-2)


def test_simulate_op_current_source_bias_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("gnd", "nout", [CurrentSource("bias", 0.002)])
    circuit.add_branch("nout", "gnd", [Resistor("load", 1000)])

    translated = circuit.simulate_op().translated_waveforms()

    assert translated.iloc[0]["V(nout)"] == pytest.approx(2.0, abs=1e-2)


def test_simulate_op_diode_bias_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_model(".MODEL DFAST D(IS=1e-9)")
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])
    circuit.add_branch("vin", "anode", [Resistor("r1", 1000)])
    circuit.add_branch("anode", "gnd", [Diode("d1", "DFAST")])

    translated = circuit.simulate_op().translated_waveforms()
    diode_node_voltage = translated.iloc[0]["V(anode)"]

    assert translated.iloc[0]["V(vin)"] == pytest.approx(5.0, abs=1e-4)
    assert 0.0 < diode_node_voltage < 5.0
