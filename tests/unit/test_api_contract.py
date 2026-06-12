from __future__ import annotations

import warnings

import networkx as nx
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import xyce_py
from xyce_py import compiler, engine, graph, models
from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import SolveResult, Subcircuit, VoltageSource


pytestmark = pytest.mark.unit


def test___all___exports_resolve_to_expected_objects():
    expected_objects = {
        "BJT": models.BJT,
        "BehavioralSource": models.BehavioralSource,
        "Capacitor": models.Capacitor,
        "CircuitElement": models.CircuitElement,
        "CircuitGraph": graph.CircuitGraph,
        "CircuitTopologyError": graph.CircuitTopologyError,
        "CurrentSource": models.CurrentSource,
        "Diode": models.Diode,
        "Inductor": models.Inductor,
        "MOSFET": models.MOSFET,
        "NTerminalDevice": models.NTerminalDevice,
        "NetlistCompiler": compiler.NetlistCompiler,
        "Resistor": models.Resistor,
        "SolveResult": models.SolveResult,
        "Subcircuit": models.Subcircuit,
        "VoltageSource": models.VoltageSource,
        "XyceExecutionResult": engine.XyceExecutionResult,
        "XyceRunError": engine.XyceRunError,
        "run_xyce_netlist": engine.run_xyce_netlist,
        "find_xyce_executable": engine.find_xyce_executable,
    }

    assert sorted(xyce_py.__all__) == sorted(expected_objects)
    for name, expected in expected_objects.items():
        assert getattr(xyce_py, name) is expected


def test_circuit_graph_constructor_resolves_base_out_dir_and_copies_solver_params(tmp_path):
    original_solver_params = {"reltol": 1e-4}

    circuit = CircuitGraph(
        xyce_path="Xyce",
        base_out_dir=str(tmp_path / "runs"),
        solver_params=original_solver_params,
    )

    assert circuit.base_out_dir == (tmp_path / "runs").resolve()
    assert circuit.solver_params == original_solver_params
    assert circuit.solver_params is not original_solver_params


def test_circuit_graph_constructor_uses_find_xyce_executable_when_xyce_path_is_none(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(graph, "find_xyce_executable", lambda: "/mock/Xyce")

    circuit = CircuitGraph(base_out_dir=str(tmp_path))

    assert circuit.xyce_path == "/mock/Xyce"


def test_voltage_source_constructor_coerces_integer_dc_value_to_float():
    source = VoltageSource("v1", 1)

    assert source.dc_value == 1.0
    assert isinstance(source.dc_value, float)


def test_subcircuit_constructor_preserves_declared_terminal_count():
    subcircuit = Subcircuit("u1", "AMP", terminals=3)

    assert subcircuit.terminals == 3
    assert subcircuit.expected_terminals == 3


def test_simulate_op_returns_solve_result(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate_op()

    assert isinstance(result, SolveResult)
    assert list(result.waveforms.columns) == ["V(N_1)", "V(N_2)"]


def test_translated_waveforms_returns_new_dataframe_without_mutating_original():
    original = pd.DataFrame({"TIME": [0.0], "V(N_1)": [5.0], "I(V_SRC)": [0.1]})
    result = SolveResult(
        original_graph=nx.MultiDiGraph(),
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=original,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vout"},
    )

    translated = result.translated_waveforms()

    assert translated is not original
    assert list(translated.columns) == ["TIME", "V(vout)", "I(V_SRC)"]
    assert list(original.columns) == ["TIME", "V(N_1)", "I(V_SRC)"]
    assert_frame_equal(original, pd.DataFrame({"TIME": [0.0], "V(N_1)": [5.0], "I(V_SRC)": [0.1]}))


def test_netlist_compiler_compile_appends_single_end_with_trailing_newline():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])

    netlist = NetlistCompiler(circuit.G, circuit.spice_directives).compile()

    assert netlist.endswith(".END\n")
    assert netlist.count(".END") == 1


def test_deprecated_simulate_signature_emits_deprecationwarning_with_expected_message(
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        circuit.simulate("OP", ".OP")

    assert len(caught) == 1
    assert caught[0].category is DeprecationWarning
    assert "deprecated" in str(caught[0].message)
    assert "use simulate(analysis_cmd, ...)" in str(caught[0].message)


def test_deprecated_simulate_signature_matches_modern_netlist_semantics(
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    modern = build_voltage_divider()
    legacy = build_voltage_divider()

    modern_result = modern.simulate(".OP")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy_result = legacy.simulate("OP", ".OP")

    assert legacy_result.netlist == modern_result.netlist
    assert list(legacy_result.waveforms.columns) == list(modern_result.waveforms.columns)
