from __future__ import annotations

import string

import networkx as nx
import pandas as pd
import pytest
from hypothesis import given, strategies as st
from pandas.testing import assert_frame_equal

from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import Resistor, SolveResult


pytestmark = pytest.mark.property


BRANCH_LENGTHS = st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=5)
EXTRA_COLUMNS = st.lists(
    st.sampled_from(["TIME", "I(V_SRC)", "V(N_3)", "V(_INT_hidden)", "PWR(Q1)"]),
    unique=True,
    max_size=5,
)


@given(branch_lengths=BRANCH_LENGTHS)
def test_grounded_graph_user_spice_mapping_invariants_under_hypothesis(branch_lengths):
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)

    for index, branch_length in enumerate(branch_lengths, start=1):
        node_id = f"n{index}"
        elements = [Resistor(f"r{index}_{step}", step + 1) for step in range(branch_length)]
        circuit.add_branch(node_id, "gnd", elements)

    compiler = NetlistCompiler(circuit.G, [])
    compiler.compile()

    assert compiler.user_to_spice_node["gnd"] == "0"
    assert list(compiler.user_to_spice_node.values()).count("0") == 1
    assert len(compiler.user_to_spice_node) == len(branch_lengths) + 1
    assert set(compiler.spice_to_user_node.values()) == set(circuit.G.nodes)


@given(branch_length=st.integers(min_value=1, max_value=6))
def test_series_branch_hidden_node_count_matches_branch_length_under_hypothesis(branch_length):
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch(
        "vin",
        "gnd",
        [Resistor(f"r{index}", index + 1) for index in range(branch_length)],
    )

    compiler = NetlistCompiler(circuit.G, [])
    compiler.compile()
    hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]

    assert len(hidden_nodes) == branch_length - 1
    assert all(len(data["elements"]) == 1 for _, _, _, data in compiler.expanded_graph.edges(keys=True, data=True))


@given(extra_columns=EXTRA_COLUMNS)
def test_translated_waveforms_only_rename_mapped_voltage_columns_under_hypothesis(extra_columns):
    original_columns = ["V(N_1)", "V(N_2)", *extra_columns]
    frame = pd.DataFrame({column: [index] for index, column in enumerate(original_columns)})
    result = SolveResult(
        original_graph=nx.MultiDiGraph(),
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=frame,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vin", "N_2": "vout"},
    )

    translated = result.translated_waveforms()

    assert "V(vin)" in translated.columns
    assert "V(vout)" in translated.columns
    for column in extra_columns:
        assert column in translated.columns
    assert_frame_equal(frame, pd.DataFrame({column: [index] for index, column in enumerate(original_columns)}))
