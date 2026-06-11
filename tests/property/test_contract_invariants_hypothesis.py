from __future__ import annotations

import string

import pandas as pd
import pytest
from hypothesis import given, strategies as st

from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Resistor, SolveResult, VoltageSource


pytestmark = pytest.mark.property


NODE_NAMES = st.text(
    alphabet=string.ascii_letters + string.digits + "_",
    min_size=1,
    max_size=12,
).filter(lambda value: value not in {"gnd"} and not value.startswith(("_DEV_", "_INT_")))


@given(branch_lengths=st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=8))
def test_compiler_line_count_and_hidden_node_count_match_branch_lengths(branch_lengths):
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)

    expected_element_lines = 0
    expected_hidden_nodes = 0
    for branch_index, branch_length in enumerate(branch_lengths):
        elements = []
        for element_index in range(branch_length):
            if element_index % 2 == 0:
                elements.append(Resistor(f"r_{branch_index}_{element_index}", element_index + 1))
            else:
                elements.append(Capacitor(f"c_{branch_index}_{element_index}", f"{element_index}u"))
        circuit.add_branch(f"n{branch_index}", "gnd", elements)
        expected_element_lines += branch_length
        expected_hidden_nodes += branch_length - 1

    compiler = NetlistCompiler(circuit.G, [])
    netlist_lines = compiler.compile().splitlines()
    hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert len(netlist_lines) == 3 + expected_element_lines
    assert len(hidden_nodes) == expected_hidden_nodes
    assert len(set(hidden_nodes)) == len(hidden_nodes)


@given(node_names=st.lists(NODE_NAMES, min_size=1, max_size=10, unique=True))
def test_default_node_mapping_is_bijective_for_user_nodes(node_names):
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch(node_names[0], "gnd", [VoltageSource("src", 1.0)])
    for index, node_name in enumerate(node_names):
        circuit.add_branch(node_name, "gnd", [Resistor(f"r{index}", index + 1)])

    compiler = NetlistCompiler(circuit.G, [])
    compiler.compile()

    assert set(compiler.node_map_forward) == set(circuit.G.nodes)
    assert set(compiler.node_map_inverse.values()) == set(circuit.G.nodes)
    assert len(compiler.node_map_forward) == len(compiler.node_map_inverse)
    assert compiler.node_map_forward["gnd"] == "0"


@given(
    mapped_count=st.integers(min_value=1, max_value=8),
    extra_columns=st.lists(
        st.one_of(
            st.sampled_from(["TIME", "FREQ", "I(V_SRC)", "V(N_999)", "P(Q1)"]),
            st.integers(min_value=0, max_value=10),
        ),
        max_size=8,
    ),
)
def test_translated_waveforms_preserve_shape_data_and_unmapped_columns(mapped_count, extra_columns):
    mapped_columns = [f"V(N_{index})" for index in range(1, mapped_count + 1)]
    columns = [*mapped_columns, *extra_columns]
    frame = pd.DataFrame([[float(index) for index in range(len(columns))]], columns=columns)
    node_map_inverse = {f"N_{index}": f"node_{index}" for index in range(1, mapped_count + 1)}
    result = SolveResult(
        original_graph=CircuitGraph(xyce_path="Xyce").G,
        expanded_graph=CircuitGraph(xyce_path="Xyce").G,
        netlist="* test\n.END\n",
        waveforms=frame,
        solve_time_sec=0.0,
        stdout="",
        node_map_inverse=node_map_inverse,
    )

    translated = result.translated_waveforms()

    assert translated.shape == frame.shape
    assert translated.to_numpy().tolist() == frame.to_numpy().tolist()
    assert list(frame.columns) == columns
    for index in range(1, mapped_count + 1):
        assert f"V(node_{index})" in translated.columns
