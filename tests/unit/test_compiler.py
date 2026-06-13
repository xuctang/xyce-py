from __future__ import annotations

import pytest

from xyce_py.compiler import NetlistBody, NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import BJT, Capacitor, Resistor, VoltageSource


pytestmark = pytest.mark.unit


def _build_series_circuit(element_count: int) -> CircuitGraph:
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_node("n1")
    elements = [Resistor(f"r{index}", index + 1) for index in range(element_count)]
    circuit.add_branch("n1", "gnd", elements)
    return circuit


def test_compile_expands_four_element_branch_into_three_hidden_nodes():
    compiler = NetlistCompiler(_build_series_circuit(4).G, [])

    compiler.compile()
    hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert hidden_nodes == ["_INT_N_1_0_0_step1", "_INT_N_1_0_0_step2", "_INT_N_1_0_0_step3"]
    assert len(list(compiler.expanded_graph.edges(keys=True))) == 4


def test_compile_expands_ten_element_branch_without_hidden_name_collisions():
    compiler = NetlistCompiler(_build_series_circuit(10).G, [])

    compiler.compile()
    hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert len(hidden_nodes) == 9
    assert len(hidden_nodes) == len(set(hidden_nodes))


def test_compile_hidden_nodes_are_unique_across_parallel_branches():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("n1", "gnd", [Resistor("r1", 1000), Capacitor("c1", "1u")])
    circuit.add_branch("n1", "gnd", [Resistor("r2", 2000), Capacitor("c2", "2u")])
    compiler = NetlistCompiler(circuit.G, [])

    compiler.compile()
    hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert hidden_nodes == ["_INT_N_1_0_0_step1", "_INT_N_1_0_1_step1"]


def test_compile_hidden_node_names_are_deterministic_across_repeated_calls():
    compiler = NetlistCompiler(_build_series_circuit(3).G, [])

    compiler.compile()
    first = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]
    compiler.compile()
    second = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert second == first


def test_compile_repeated_calls_reset_expanded_graph_state():
    compiler = NetlistCompiler(_build_series_circuit(5).G, [])

    compiler.compile()
    first_edge_count = len(list(compiler.expanded_graph.edges(keys=True)))
    compiler.compile()
    second_edge_count = len(list(compiler.expanded_graph.edges(keys=True)))

    assert first_edge_count == second_edge_count == 5


def test_compile_preserves_directive_then_element_then_device_order():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_model(".MODEL DFAST D(IS=1e-9)")
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])
    circuit.add_branch("collector", "gnd", [Resistor("load", 1000)])
    circuit.add_device(BJT("amp", "QMOD"), ["collector", "base", "gnd"])
    compiler = NetlistCompiler(circuit.G, circuit.spice_directives)

    lines = compiler.compile().splitlines()

    assert lines[0] == "* Generated Circuit"
    assert lines[1] == ".MODEL DFAST D(IS=1e-9)"
    assert lines[2] == ".OPTIONS DEVICE GMIN=1e-8"
    assert lines[3].startswith("V_src ")
    assert lines[4].startswith("R_load ")
    assert lines[5].startswith("Q_amp ")


def test_compile_places_caller_options_after_generated_default_options():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_model(".MODEL DFAST D(IS=1e-9)")
    circuit.add_options(".OPTIONS NONLIN RELTOL=1e-4")
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])
    compiler = NetlistCompiler(circuit.G, circuit.spice_directives)

    lines = compiler.compile().splitlines()

    assert lines[1] == ".MODEL DFAST D(IS=1e-9)"
    assert lines[2] == ".OPTIONS DEVICE GMIN=1e-8"
    assert lines[3] == ".OPTIONS NONLIN RELTOL=1e-4"
    assert lines[4].startswith("V_src ")


def test_compile_handles_device_only_grounded_graph():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("amp", "QMOD"), ["collector", "base", "gnd"])
    compiler = NetlistCompiler(circuit.G, [])

    netlist = compiler.compile()

    assert "Q_amp N_1 N_2 0 QMOD" in netlist
    assert netlist.endswith(".END\n")


def test_compile_handles_directive_only_grounded_graph():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_model(".MODEL DFAST D(IS=1e-9)")
    compiler = NetlistCompiler(circuit.G, circuit.spice_directives)

    netlist = compiler.compile()

    assert netlist == "* Generated Circuit\n.MODEL DFAST D(IS=1e-9)\n.OPTIONS DEVICE GMIN=1e-8\n.END\n"


def test_compile_appends_end_exactly_once():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    netlist = compiler.compile()

    assert netlist.count(".END") == 1
    assert netlist.endswith(".END\n")


def test_compile_body_returns_public_compiler_result_without_end_line():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    compiled_body = compiler.compile_body()

    assert isinstance(compiled_body, NetlistBody)
    assert compiled_body.lines[-1].startswith("R_r0 ")
    assert ".END" not in compiled_body.lines
    assert compiled_body.user_to_spice_node == compiler.user_to_spice_node
    assert compiled_body.spice_to_user_node == compiler.spice_to_user_node
    assert compiled_body.expanded_graph is not compiler.expanded_graph


def test_compile_body_exposes_read_only_user_spice_node_mappings():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    compiled_body = compiler.compile_body()

    with pytest.raises(TypeError):
        compiled_body.user_to_spice_node["n1"] = "changed"
    with pytest.raises(TypeError):
        compiled_body.spice_to_user_node["N_1"] = "changed"


def test_compile_body_expanded_graph_is_independent_from_compiler_state():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    compiled_body = compiler.compile_body()
    compiled_body.expanded_graph.add_node("body_only")

    assert "body_only" not in compiler.expanded_graph


def test_compiler_public_state_properties_are_defensive():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    compiler.compile()
    with pytest.raises(TypeError):
        compiler.user_to_spice_node["n1"] = "changed"
    with pytest.raises(TypeError):
        compiler.spice_to_user_node["N_1"] = "changed"

    expanded_graph = compiler.expanded_graph
    expanded_graph.add_node("external_only")

    assert "external_only" not in compiler.expanded_graph


def test_compile_user_spice_node_mappings_are_stable_across_repeated_calls():
    compiler = NetlistCompiler(_build_series_circuit(2).G, [])

    compiler.compile()
    first_user_to_spice_node = compiler.user_to_spice_node.copy()
    first_spice_to_user_node = compiler.spice_to_user_node.copy()
    compiler.compile()

    assert compiler.user_to_spice_node == first_user_to_spice_node
    assert compiler.spice_to_user_node == first_spice_to_user_node


def test_compile_expanded_graph_preserves_source_graph_metadata():
    circuit = _build_series_circuit(1)
    circuit.G.graph["source"] = "unit-test"
    circuit.G.nodes["n1"]["label"] = "input"
    circuit.G.edges["n1", "gnd", 0]["tag"] = "load"
    compiler = NetlistCompiler(circuit.G, [])

    compiler.compile()

    assert compiler.expanded_graph.graph["source"] == "unit-test"
    assert compiler.expanded_graph.nodes["n1"]["label"] == "input"
    assert compiler.expanded_graph.edges["n1", "gnd", 0]["tag"] == "load"
