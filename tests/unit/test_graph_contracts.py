from __future__ import annotations

import pytest

from xyce_py.graph import CircuitGraph, CircuitTopologyError
from xyce_py.models import BJT, MOSFET, Resistor, VoltageSource


pytestmark = pytest.mark.unit


def test_add_node_can_mark_existing_node_as_ground_once():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd")

    circuit.add_node("gnd", is_ground=True)
    circuit.add_node("gnd", is_ground=True)

    assert circuit.G.nodes["gnd"]["is_ground"] is True
    assert circuit._find_ground_node() == "gnd"


@pytest.mark.parametrize("reserved_node_id", ["_DEV_user", "_INT_user"])
def test_public_graph_apis_reject_reserved_user_node_prefixes(reserved_node_id):
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError, match="reserved prefixes"):
        circuit.add_branch(reserved_node_id, "gnd", [Resistor("r1", 1)])

    with pytest.raises(ValueError, match="reserved prefixes"):
        circuit.add_device(BJT("q1", "QMOD"), [reserved_node_id, "base", "emitter"])


def test_add_device_copies_ordered_terminal_list_from_caller():
    terminals = ["collector", "base", "emitter"]
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_device(BJT("q1", "QMOD"), terminals)
    terminals[0] = "changed"

    assert circuit.G.nodes["_DEV_q1"]["ordered_nodes"] == ["collector", "base", "emitter"]


def test_add_device_rejects_name_collision_before_adding_new_terminals():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_device(BJT("q1", "QMOD"), ["c", "b", "e"])

    with pytest.raises(ValueError, match="already exists"):
        circuit.add_device(BJT("q1", "QMOD2"), ["x", "y", "z"])

    assert "x" not in circuit.G
    assert "y" not in circuit.G
    assert "z" not in circuit.G


def test_add_device_creates_only_device_link_edges_for_terminals():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_device(MOSFET("m1", "NMOS"), ["d", "g", "s", "b"])

    edges = list(circuit.G.edges("_DEV_m1", data=True))

    assert len(edges) == 4
    assert all(data == {"is_device_link": True} for _, _, data in edges)


@pytest.mark.parametrize(
    ("method_name", "directive", "message"),
    [
        ("add_model", ".model DFAST D", "model_string must start with '.MODEL'."),
        ("add_model", " .MODEL DFAST D", "model_string must start with '.MODEL'."),
        ("add_options", ".options DEVICE GMIN=1e-8", "options_string must start with '.OPTIONS'."),
        ("add_options", " .OPTIONS DEVICE GMIN=1e-8", "options_string must start with '.OPTIONS'."),
    ],
)
def test_directive_helpers_are_case_and_prefix_strict(method_name, directive, message):
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError, match=message):
        getattr(circuit, method_name)(directive)


def test_directive_helpers_preserve_valid_directives_verbatim():
    circuit = CircuitGraph(xyce_path="Xyce")

    circuit.add_model(".MODEL DFAST D(IS=1e-9)")
    circuit.add_options(".OPTIONS DEVICE GMIN=1e-9")

    assert circuit.spice_directives == [
        ".MODEL DFAST D(IS=1e-9)",
        ".OPTIONS DEVICE GMIN=1e-9",
    ]


def test_add_subcircuit_preserves_internal_formatting_while_stripping_outer_whitespace():
    circuit = CircuitGraph(xyce_path="Xyce")
    subckt = "  .SUBCKT BUF IN OUT\n+ PARAMS: GAIN=2\nR1 OUT IN {GAIN}k\n.ENDS  "

    circuit.add_subcircuit(subckt)

    assert circuit.spice_directives == [
        ".SUBCKT BUF IN OUT\n+ PARAMS: GAIN=2\nR1 OUT IN {GAIN}k\n.ENDS"
    ]


def test_validate_topology_accepts_direction_reversed_paths_to_ground():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("gnd", "n1", [VoltageSource("src", 1.0)])
    circuit.add_branch("n2", "n1", [Resistor("r1", 1.0)])

    circuit._validate_topology()


def test_validate_topology_rejects_device_component_without_ground_connection():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_device(BJT("q1", "QMOD"), ["collector", "base", "emitter"])

    with pytest.raises(CircuitTopologyError, match="Floating subgraph"):
        circuit._validate_topology()


def test_constructor_solver_params_are_independent_from_caller_dict(tmp_path):
    params = {"NONLIN": {"RELTOL": 1e-4}}
    circuit = CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path), solver_params=params)

    params["NONLIN"]["RELTOL"] = 1e-2

    assert circuit.solver_params == {"NONLIN": {"RELTOL": "0.0001"}}


@pytest.mark.parametrize("bad_solver_params", [{"RELTOL": 1e-4}, {"NONLIN": {}}, {"NONLIN": {"": 1}}])
def test_constructor_solver_params_reject_ambiguous_or_invalid_shape(tmp_path, bad_solver_params):
    with pytest.raises((TypeError, ValueError)):
        CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path), solver_params=bad_solver_params)
