from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Inductor, Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_simulate_tran_rc_charge_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 0.0, "PULSE(0 1 0 1u 1u 10u 20u)")])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Capacitor("c1", "1u")])

    translated = circuit.simulate_transient("1u", "20u").translated_waveforms()

    assert "TIME" in translated.columns
    assert "V(vout)" in translated.columns
    assert translated["V(vout)"].iloc[-1] > translated["V(vout)"].iloc[0]


def test_simulate_tran_rl_step_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 0.0, "PULSE(0 1 0 1u 1u 10u 20u)")])
    circuit.add_branch("vin", "vout", [Inductor("l1", "1m")])
    circuit.add_branch("vout", "gnd", [Resistor("r1", 100)])

    translated = circuit.simulate_transient("1u", "20u").translated_waveforms()

    assert "V(vout)" in translated.columns
    assert translated["V(vout)"].iloc[-1] > translated["V(vout)"].iloc[0]


def test_simulate_tran_pulse_source_with_start_offset_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 0.0, "PULSE(0 1 5u 1u 1u 10u 25u)")])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Capacitor("c1", "1n")])

    translated = circuit.simulate_transient("1u", "25u").translated_waveforms()

    assert translated["V(vout)"].iloc[0] == pytest.approx(0.0, abs=1e-3)
    assert translated["V(vout)"].max() > 0.1
