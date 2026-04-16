from __future__ import annotations

import pytest

from xyce_py.compiler import NetlistCompiler
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
    compiler = NetlistCompiler(circuit.G, circuit.global_directives)

    lines = compiler.compile().splitlines()

    assert lines[0] == "* Generated Circuit"
    assert lines[1] == ".MODEL DFAST D(IS=1e-9)"
    assert lines[2] == ".OPTIONS DEVICE GMIN=1e-8"
    assert lines[3].startswith("V_src ")
    assert lines[4].startswith("R_load ")
    assert lines[5].startswith("Q_amp ")


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
    compiler = NetlistCompiler(circuit.G, circuit.global_directives)

    netlist = compiler.compile()

    assert netlist == "* Generated Circuit\n.MODEL DFAST D(IS=1e-9)\n.OPTIONS DEVICE GMIN=1e-8\n.END\n"


def test_compile_appends_end_exactly_once():
    compiler = NetlistCompiler(_build_series_circuit(1).G, [])

    netlist = compiler.compile()

    assert netlist.count(".END") == 1
    assert netlist.endswith(".END\n")


def test_compile_node_maps_are_stable_across_repeated_calls():
    compiler = NetlistCompiler(_build_series_circuit(2).G, [])

    compiler.compile()
    first_forward = compiler.node_map_forward.copy()
    first_inverse = compiler.node_map_inverse.copy()
    compiler.compile()

    assert compiler.node_map_forward == first_forward
    assert compiler.node_map_inverse == first_inverse
