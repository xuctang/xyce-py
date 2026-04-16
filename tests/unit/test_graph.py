from __future__ import annotations

from enum import Enum

import pytest

from xyce_py.graph import CircuitGraph, CircuitTopologyError
from xyce_py.models import BJT, Resistor


pytestmark = pytest.mark.unit


class ProbeNode(Enum):
    INPUT = 1


def test_add_node_accepts_hashable_non_string_identifiers():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_node(1)
    circuit.add_node(("tuple", 2))
    circuit.add_node(ProbeNode.INPUT)

    assert 1 in circuit.G
    assert ("tuple", 2) in circuit.G
    assert ProbeNode.INPUT in circuit.G


def test_add_node_allows_literal_zero_without_ground_flag():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_node("0")

    assert "0" in circuit.G
    assert "is_ground" not in circuit.G.nodes["0"]


def test_add_node_allows_nonzero_ground_alias_when_marked_ground():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_node("gnd", is_ground=True)

    assert circuit.G.nodes["gnd"]["is_ground"] is True


def test_add_node_rejects_unhashable_input():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(TypeError, match="node_id must be hashable."):
        circuit.add_node([])


def test_add_node_rejects_reserved_internal_prefixes():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError):
        circuit.add_node("_DEV_user")

    with pytest.raises(ValueError):
        circuit.add_node("_INT_hidden")


def test_add_node_rejects_second_distinct_ground():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)

    with pytest.raises(ValueError, match="Only one ground node may be defined in the graph."):
        circuit.add_node("0", is_ground=True)


def test_add_branch_allows_self_loop():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("n1")

    circuit.add_branch("n1", "n1", [Resistor("r1", 1000)])

    assert ("n1", "n1", 0) in list(circuit.G.edges(keys=True))


def test_add_branch_allows_ground_to_ground_branch():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)

    circuit.add_branch("gnd", "gnd", [Resistor("r1", 1000)])

    assert ("gnd", "gnd", 0) in list(circuit.G.edges(keys=True))


def test_add_branch_preserves_twenty_element_series_order():
    circuit = CircuitGraph(xyce_path="Xyce")
    elements = [Resistor(f"r{index}", index) for index in range(20)]

    circuit.add_branch("n1", "n2", elements)

    assert circuit.G.edges["n1", "n2", 0]["elements"] == elements


def test_add_branch_allows_parallel_multi_element_edges_between_same_endpoints():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_branch("n1", "n2", [Resistor("r1", 1000), Resistor("r2", 2000)])
    circuit.add_branch("n1", "n2", [Resistor("r3", 3000), Resistor("r4", 4000)])

    assert len(list(circuit.G.edges(keys=True))) == 2


def test_add_branch_rejects_invalid_element_containers():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(TypeError, match="elements must be provided as a list"):
        circuit.add_branch("n1", "n2", (Resistor("r1", 1000),))

    with pytest.raises(ValueError, match="elements must be a non-empty list"):
        circuit.add_branch("n1", "n2", [])

    with pytest.raises(TypeError, match="elements must contain only CircuitElement instances."):
        circuit.add_branch("n1", "n2", [Resistor("r1", 1000), "bad"])


def test_add_device_accepts_repeated_node_ids_when_arity_matches():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_device(BJT("amp", "QMOD"), ["collector", "collector", "gnd"])

    assert "_DEV_amp" in circuit.G
    assert len(list(circuit.G.edges("_DEV_amp", keys=True))) == 3


def test_add_device_rejects_invalid_inputs_and_collisions():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(TypeError, match="device must be an NTerminalDevice instance."):
        circuit.add_device(Resistor("r1", 1000), ["n1", "n2"])

    with pytest.raises(TypeError, match="nodes must be provided as a list of node identifiers."):
        circuit.add_device(BJT("amp", "QMOD"), ("c", "b", "e"))

    with pytest.raises(ValueError, match="nodes must contain exactly 3 node identifiers."):
        circuit.add_device(BJT("amp", "QMOD"), ["c", "b"])

    circuit.add_device(BJT("amp", "QMOD"), ["c", "b", "e"])
    with pytest.raises(ValueError, match="Device node '_DEV_amp' already exists in the graph."):
        circuit.add_device(BJT("amp", "QMOD"), ["x", "y", "z"])


def test_add_model_and_options_reject_invalid_directives():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError, match="model_string must start with '.MODEL'."):
        circuit.add_model(".OPTIONS DEVICE GMIN=1e-8")

    with pytest.raises(ValueError, match="options_string must start with '.OPTIONS'."):
        circuit.add_options(".MODEL DFAST D")


def test_validate_topology_accepts_ground_plus_device_links_only():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("amp", "QMOD"), ["collector", "base", "gnd"])

    circuit._validate_topology()


def test_validate_topology_rejects_empty_graph():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(CircuitTopologyError, match="Circuit has no ground reference."):
        circuit._validate_topology()


def test_validate_topology_rejects_multiple_ground_nodes():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_node("alias")
    circuit.G.nodes["alias"]["is_ground"] = True

    with pytest.raises(CircuitTopologyError, match="Circuit has multiple ground references."):
        circuit._validate_topology()


def test_validate_topology_rejects_ground_plus_isolated_user_node():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_node("floating")

    with pytest.raises(CircuitTopologyError, match="Floating subgraph detected with no path to ground."):
        circuit._validate_topology()


def test_find_ground_node_returns_none_and_ground_node():
    circuit = CircuitGraph(xyce_path="Xyce")
    assert circuit._find_ground_node() is None

    circuit.add_node("gnd", is_ground=True)

    assert circuit._find_ground_node() == "gnd"


def test_add_subcircuit_strips_outer_whitespace_before_validation():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_subcircuit("  .SUBCKT BUF IN OUT\nR1 OUT IN 1k\n.ENDS  ")

    assert circuit.global_directives == [".SUBCKT BUF IN OUT\nR1 OUT IN 1k\n.ENDS"]


def test_add_subcircuit_rejects_invalid_directives():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError, match="subckt_string must start with '.SUBCKT'."):
        circuit.add_subcircuit("R1 OUT IN 1k\n.ENDS")

    with pytest.raises(ValueError, match="subckt_string must end with '.ENDS'."):
        circuit.add_subcircuit(".SUBCKT BUF IN OUT\nR1 OUT IN 1k")
