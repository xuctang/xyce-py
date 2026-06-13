from __future__ import annotations

import pytest

from xyce_py import CircuitGraph, OutputSpec, Resistor, VoltageSource, XyceProject


pytestmark = pytest.mark.xyce


def test_raw_netlist_project_runs_exact_netlist_with_real_xyce(tmp_path, xyce_path_or_skip):
    project = XyceProject(
        "raw-voltage-divider",
        """* raw voltage divider
V1 1 0 DC 10
R1 1 2 1000
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=raw.csv V(1) V(2)
.END
""",
        output_specs=(OutputSpec.csv("waveforms", "raw.csv"),),
    )

    result = project.run(xyce_path=xyce_path_or_skip, base_out_dir=tmp_path)

    frame = result.outputs["waveforms"].frame
    assert len(frame) == 1
    assert frame.iloc[0]["V(1)"] == pytest.approx(10.0, abs=1e-4)
    assert frame.iloc[0]["V(2)"] == pytest.approx(5.0, abs=1e-2)


def test_graph_compile_project_runs_generated_raw_project_with_real_xyce(tmp_path, xyce_path_or_skip):
    circuit = CircuitGraph(xyce_path=xyce_path_or_skip, base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [Resistor("r2", 1000)])
    body = circuit.compile_body()

    project = circuit.compile_project(
        "compiled-graph-project",
        [
            ".OP",
            f".PRINT DC FORMAT=CSV FILE=compiled.csv V({body.user_to_spice_node['vout']})",
        ],
        output_specs=(OutputSpec.csv("waveforms", "compiled.csv"),),
    )

    result = project.run(xyce_path=xyce_path_or_skip, base_out_dir=tmp_path)

    frame = result.output("waveforms").frame
    assert len(frame) == 1
    assert frame.iloc[0]["V(N_2)"] == pytest.approx(5.0, abs=1e-2)
