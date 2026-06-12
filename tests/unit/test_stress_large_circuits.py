from __future__ import annotations

import pandas as pd
import pytest

from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Resistor, VoltageSource


pytestmark = pytest.mark.unit


def _build_large_circuit() -> CircuitGraph:
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])

    previous_node = "vin"
    for index in range(1, 16):
        node_id = f"n{index}"
        branch_elements = [Resistor(f"series_r{index}", 1000 + index * 10)]
        if index % 3 == 0:
            branch_elements.append(Capacitor(f"series_c{index}", f"{index}u"))
        circuit.add_branch(previous_node, node_id, branch_elements)
        circuit.add_branch(node_id, "gnd", [Resistor(f"shunt_r{index}", 2000 + index * 100)])
        previous_node = node_id

    return circuit


def _hidden_nodes(graph) -> list[str]:
    return sorted(node for node, data in graph.nodes(data=True) if data.get("is_hidden"))


def test_large_circuit_compile_is_stable_across_repeated_runs():
    circuit = _build_large_circuit()
    compiler = NetlistCompiler(circuit.G, circuit.spice_directives)

    baseline_netlist = compiler.compile()
    baseline_user_to_spice_node = compiler.user_to_spice_node.copy()
    baseline_spice_to_user_node = compiler.spice_to_user_node.copy()
    baseline_hidden_nodes = _hidden_nodes(compiler.expanded_graph)
    baseline_edge_count = len(list(compiler.expanded_graph.edges(keys=True)))

    for _ in range(3):
        netlist = compiler.compile()
        assert netlist == baseline_netlist
        assert compiler.user_to_spice_node == baseline_user_to_spice_node
        assert compiler.spice_to_user_node == baseline_spice_to_user_node
        assert _hidden_nodes(compiler.expanded_graph) == baseline_hidden_nodes
        assert len(list(compiler.expanded_graph.edges(keys=True))) == baseline_edge_count

    assert not any(isinstance(node, str) and node.startswith("_INT_") for node in circuit.G.nodes)


def test_large_circuit_simulate_is_stable_and_does_not_leak_internal_state(stub_xyce_execution):
    circuit = _build_large_circuit()
    stub_xyce_execution(
        waveforms=pd.DataFrame(
            {
                "V(N_1)": [10.0],
                "V(N_2)": [9.5],
                "V(N_3)": [9.0],
            }
        )
    )

    baseline_node_count = len(circuit.G.nodes)
    baseline_edge_count = len(circuit.G.edges)
    results = [circuit.simulate(".OP", print_vars=["V(N_1)", "V(N_2)", "V(N_3)"]) for _ in range(3)]

    assert all(result.netlist == results[0].netlist for result in results[1:])
    assert all(result.spice_to_user_node == results[0].spice_to_user_node for result in results[1:])
    assert all(_hidden_nodes(result.expanded_graph) == _hidden_nodes(results[0].expanded_graph) for result in results[1:])
    assert len(circuit.G.nodes) == baseline_node_count
    assert len(circuit.G.edges) == baseline_edge_count
    assert not any(isinstance(node, str) and node.startswith("_INT_") for node in circuit.G.nodes)
