from __future__ import annotations

import pandas as pd
import pytest

import xyce_py.graph as graph_module
from xyce_py.engine import XyceRunError
from xyce_py.graph import CircuitGraph
from xyce_py.models import BJT, Capacitor, Resistor, VoltageSource


pytestmark = pytest.mark.unit


def test_simulate_passes_exact_execution_contract_to_engine(build_voltage_divider, stub_xyce_execution):
    calls = stub_xyce_execution()
    circuit = build_voltage_divider(xyce_path="/mock/Xyce")

    result = circuit.simulate(".OP")

    assert len(calls) == 1
    call = calls[0]
    assert call["xyce_path"] == "/mock/Xyce"
    assert call["base_out_dir"] == circuit.base_out_dir
    assert call["csv_name"] == "output.csv"
    assert call["run_name"].startswith("simulate_op_")
    assert call["keep_run_dir"] is False
    assert call["netlist_content"] == result.netlist


@pytest.mark.parametrize(
    ("analysis_cmd", "analysis_type"),
    [
        (".op", "DC"),
        (".TRAN 1u 10u", "TRAN"),
        (".ac DEC 5 1 1e3", "AC"),
        (".dc V_src 0 1 0.1", "DC"),
    ],
)
def test_simulate_infers_analysis_type_case_insensitively(
    analysis_cmd,
    analysis_type,
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(analysis_cmd)

    assert f".PRINT {analysis_type} FORMAT=CSV FILE=output.csv" in result.netlist
    assert analysis_cmd.strip() in result.netlist


def test_simulate_preserves_custom_print_var_order_and_skips_default_print_vars(
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP", print_vars=["I(V_src)", "V(N_2)"])

    assert ".PRINT DC FORMAT=CSV FILE=output.csv I(V_src) V(N_2)" in result.netlist
    assert ".PRINT DC FORMAT=CSV FILE=output.csv V(N_1) V(N_2)" not in result.netlist


def test_default_print_vars_include_only_non_ground_mapped_user_nodes(stub_xyce_execution, tmp_path):
    stub_xyce_execution()
    circuit = CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("q1", "QMOD"), ["collector", "base", "gnd"])

    result = circuit.simulate(".OP")

    assert ".PRINT DC FORMAT=CSV FILE=output.csv V(N_1) V(N_2)" in result.netlist
    assert "V(0)" not in result.netlist
    assert "_DEV_q1" not in result.netlist


@pytest.mark.parametrize(
    ("method_name", "args", "error_message"),
    [
        ("simulate_transient", ("1u", 10), "stop must be a string."),
        ("simulate_transient", ("1u", "10u", 0), "start must be a string."),
        ("simulate_ac", ("DEC", 10, "1", "1e3"), "points must be a string."),
        ("simulate_ac", ("DEC", "10", 1, "1e3"), "start_freq must be a string."),
        ("simulate_ac", ("DEC", "10", "1", 1000), "stop_freq must be a string."),
        ("simulate_dc", ("V_src", 0, "1", "0.1"), "start must be a string."),
        ("simulate_dc", ("V_src", "0", 1, "0.1"), "stop must be a string."),
        ("simulate_dc", ("V_src", "0", "1", 0.1), "step must be a string."),
    ],
)
def test_simulation_wrappers_validate_every_string_argument(
    method_name,
    args,
    error_message,
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(TypeError, match=error_message):
        getattr(circuit, method_name)(*args)


def test_inplace_solution_is_atomic_when_existing_solved_voltage_is_detected(
    build_voltage_divider,
    stub_xyce_execution,
):
    waveforms = pd.DataFrame({"V(N_1)": [10.0], "V(N_2)": [5.0]})
    stub_xyce_execution(waveforms=waveforms)
    circuit = build_voltage_divider()
    circuit.G.nodes["vout"]["solved_voltage"] = 99.0

    with pytest.raises(RuntimeError, match="Attribute 'solved_voltage' already exists"):
        circuit.simulate(".OP", inplace=True)

    assert "solved_voltage" not in circuit.G.nodes["vin"]
    assert circuit.G.nodes["vout"]["solved_voltage"] == 99.0


def test_xyce_execution_error_propagates_without_mutating_graph(monkeypatch, build_voltage_divider):
    def _raise_error(**kwargs):
        raise XyceRunError("solver failed", returncode=1)

    monkeypatch.setattr(graph_module, "_execute_xyce_netlist", _raise_error)
    circuit = build_voltage_divider()

    with pytest.raises(XyceRunError, match="solver failed"):
        circuit.simulate(".OP", inplace=True)

    assert "solved_voltage" not in circuit.G.nodes["vin"]
    assert "solved_voltage" not in circuit.G.nodes["vout"]


def test_simulate_fails_fast_if_compiler_does_not_produce_expanded_graph(
    monkeypatch,
    build_voltage_divider,
    stub_xyce_execution,
):
    class BrokenCompiler:
        def __init__(self, graph, global_directives):
            self.node_map_forward = {"vin": "N_1", "vout": "N_2", "gnd": "0"}
            self.node_map_inverse = {"N_1": "vin", "N_2": "vout", "0": "gnd"}
            self.expanded_graph = None

        def _compile_body_lines(self):
            return ["* Generated Circuit", ".OPTIONS DEVICE GMIN=1e-8"]

    monkeypatch.setattr(graph_module, "NetlistCompiler", BrokenCompiler)
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(RuntimeError, match="Compiler did not produce an expanded graph."):
        circuit.simulate(".OP")


def test_simulate_result_graph_snapshots_are_independent_after_return(stub_xyce_execution, tmp_path):
    stub_xyce_execution()
    circuit = CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 1.0)])

    result = circuit.simulate(".OP")
    circuit.add_branch("later", "gnd", [Resistor("r_later", 1.0)])

    assert "later" not in result.original_graph
    assert "later" not in result.expanded_graph


def test_simulate_result_expanded_graph_contains_hidden_nodes_for_series_branches(stub_xyce_execution, tmp_path):
    stub_xyce_execution()
    circuit = CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 1.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1.0), Capacitor("c1", "1u")])

    result = circuit.simulate(".OP")

    hidden_nodes = [node for node, data in result.expanded_graph.nodes(data=True) if data.get("is_hidden")]
    assert hidden_nodes == ["_INT_N_1_N_2_0_step1"]
