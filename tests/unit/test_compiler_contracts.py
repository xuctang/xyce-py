from __future__ import annotations

import networkx as nx
import pytest

from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import BJT, Capacitor, Resistor, VoltageSource


pytestmark = pytest.mark.unit


def test_compile_exact_netlist_for_mixed_branch_and_device_topology():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_model(".MODEL QMOD NPN")
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])
    circuit.add_branch("vin", "vout", [Resistor("r1", 1000), Capacitor("c1", "1u")])
    circuit.add_device(BJT("amp", "QMOD"), ["vout", "vin", "gnd"])

    netlist = NetlistCompiler(circuit.G, circuit.spice_directives).compile()

    assert netlist == (
        "* Generated Circuit\n"
        ".MODEL QMOD NPN\n"
        ".OPTIONS DEVICE GMIN=1e-8\n"
        "V_src N_1 0 DC 5.0\n"
        "R_r1 N_1 _INT_N_1_N_2_0_step1 1000.0\n"
        "C_c1 _INT_N_1_N_2_0_step1 N_2 1u\n"
        "Q_amp N_2 N_1 0 QMOD\n"
        ".END\n"
    )


def test_compile_does_not_mutate_source_graph_when_expanding_series_branch():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    elements = [Resistor("r1", 1), Capacitor("c1", "1u")]
    circuit.add_branch("n1", "gnd", elements)
    before_nodes = list(circuit.G.nodes(data=True))
    before_edges = list(circuit.G.edges(keys=True, data=True))

    NetlistCompiler(circuit.G, []).compile()

    assert list(circuit.G.nodes(data=True)) == before_nodes
    assert list(circuit.G.edges(keys=True, data=True)) == before_edges
    assert not any(isinstance(node, str) and node.startswith("_INT_") for node in circuit.G.nodes)


def test_expanded_graph_contains_split_edges_without_original_multi_element_edge():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    r1 = Resistor("r1", 1)
    c1 = Capacitor("c1", "1u")
    circuit.add_branch("n1", "gnd", [r1, c1])
    compiler = NetlistCompiler(circuit.G, [])

    compiler.compile()

    expanded_edges = list(compiler.expanded_graph.edges(keys=True, data=True))
    assert len(expanded_edges) == 2
    assert ("n1", "gnd", 0) not in [(u, v, key) for u, v, key, _ in expanded_edges]
    assert expanded_edges[0][3]["elements"] == [r1]
    assert expanded_edges[1][3]["elements"] == [c1]


def test_device_link_edges_are_preserved_in_expanded_graph_but_not_emitted_as_netlist_lines():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("q1", "QMOD"), ["collector", "base", "gnd"])
    compiler = NetlistCompiler(circuit.G, [])

    netlist = compiler.compile()

    assert "is_device_link" not in netlist
    assert netlist.count("Q_q1") == 1
    assert len([edge for edge in compiler.expanded_graph.edges(data=True) if edge[2].get("is_device_link")]) == 3


def test_user_spice_node_mappings_skip_internal_device_nodes_and_map_exactly_one_ground():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("q1", "QMOD"), ["collector", "base", "gnd"])
    compiler = NetlistCompiler(circuit.G, [])

    compiler.compile()

    assert "_DEV_q1" not in compiler.user_to_spice_node
    assert compiler.user_to_spice_node["gnd"] == "0"
    assert list(compiler.user_to_spice_node.values()).count("0") == 1
    assert compiler.spice_to_user_node["0"] == "gnd"


def test_compile_preserves_graph_subclass_for_expanded_graph():
    class CustomMultiDiGraph(nx.MultiDiGraph):
        pass

    graph = CustomMultiDiGraph()
    graph.add_node("gnd", is_ground=True)
    graph.add_node("n1")
    graph.add_edge("n1", "gnd", elements=[Resistor("r1", 1)])
    compiler = NetlistCompiler(graph, [])

    compiler.compile()

    assert isinstance(compiler.expanded_graph, CustomMultiDiGraph)


def test_compile_does_not_mutate_spice_directives_list():
    directives = [".MODEL DFAST D(IS=1e-9)"]
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    compiler = NetlistCompiler(circuit.G, directives)

    compiler.compile()

    assert directives == [".MODEL DFAST D(IS=1e-9)"]


def test_compile_fails_fast_for_non_device_edge_missing_elements_contract():
    graph = nx.MultiDiGraph()
    graph.add_node("gnd", is_ground=True)
    graph.add_node("n1")
    graph.add_edge("n1", "gnd")

    with pytest.raises(KeyError):
        NetlistCompiler(graph, []).compile()
