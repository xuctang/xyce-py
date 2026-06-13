from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph
from xyce_py.models import Resistor, VoltageSource


pytestmark = pytest.mark.xyce


def test_xyce_runner_smoke_voltage_divider_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Resistor("r2", 1000)])

    translated = circuit.simulate_op().translated_waveforms()

    assert translated.iloc[0]["V(vin)"] == pytest.approx(10.0, abs=1e-4)
    assert translated.iloc[0]["V(vout)"] == pytest.approx(5.0, abs=1e-2)
