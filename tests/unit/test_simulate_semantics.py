from __future__ import annotations

import pandas as pd
import pytest

import xyce_py.graph as graph_module
from xyce_py.graph import CircuitGraph
from xyce_py.models import VoltageSource


pytestmark = pytest.mark.unit


def test_simulate_accepts_op_directive(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")

    assert ".OP" in result.netlist


def test_simulate_accepts_tran_directive(build_transient_graph, stub_xyce_execution):
    stub_xyce_execution(
        waveforms=pd.DataFrame({"TIME": [0.0, 1.0], "V(N_1)": [0.0, 1.0], "V(N_2)": [0.0, 0.5]})
    )
    circuit = build_transient_graph()

    result = circuit.simulate(".TRAN 1u 10u")

    assert ".TRAN 1u 10u" in result.netlist


def test_simulate_accepts_ac_directive(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution(waveforms=pd.DataFrame({"FREQ": [1.0], "V(N_1)": [10.0], "V(N_2)": [5.0]}))
    circuit = build_voltage_divider()

    result = circuit.simulate(".AC DEC 10 1 1e6")

    assert ".AC DEC 10 1 1e6" in result.netlist


def test_simulate_accepts_dc_directive(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution(waveforms=pd.DataFrame({"V(N_1)": [0.0, 10.0], "V(N_2)": [0.0, 5.0]}))
    circuit = build_voltage_divider()

    result = circuit.simulate(".DC V_src 0 10 1")

    assert ".DC V_src 0 10 1" in result.netlist


def test_simulate_strips_analysis_directive_whitespace(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate("  .OP  ")

    assert ".OP" in result.netlist
    assert "  .OP  " not in result.netlist


def test_simulate_rejects_unknown_analysis_directive(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(ValueError, match=r"\.OP, \.TRAN, \.AC, \.DC"):
        circuit.simulate(".NOISE")


def test_simulate_rejects_missing_dot_in_analysis_directive(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(ValueError, match="analysis_cmd must start with a SPICE analysis directive"):
        circuit.simulate("OP")


def test_simulate_defaults_print_vars_to_all_non_ground_user_nodes(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")

    assert ".PRINT DC FORMAT=CSV FILE=output.csv V(N_1) V(N_2)" in result.netlist


def test_simulate_rejects_empty_print_vars(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(ValueError, match="print_vars must be a non-empty list of strings."):
        circuit.simulate(".OP", print_vars=[])


def test_simulate_rejects_non_list_print_vars(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(ValueError, match="print_vars must be a non-empty list of strings."):
        circuit.simulate(".OP", print_vars="V(N_1)")


def test_simulate_rejects_non_string_print_var_entries(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(TypeError, match="print_vars item must be a string."):
        circuit.simulate(".OP", print_vars=["V(N_1)", 7])


def test_simulate_builds_netlist_with_single_print_and_end(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")

    assert result.netlist.count(".PRINT") == 1
    assert result.netlist.endswith(".END\n")


def test_simulate_op_uses_print_dc_not_print_op(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")

    assert ".PRINT DC" in result.netlist
    assert ".PRINT OP" not in result.netlist


def test_simulate_inplace_applies_only_recognized_non_ground_voltage_columns(
    build_voltage_divider,
    stub_xyce_execution,
):
    waveforms = pd.DataFrame({"V(N_1)": [10.0], "V(N_2)": [5.0], "V(0)": [0.0], "V(N_999)": [9.0]})
    stub_xyce_execution(waveforms=waveforms)
    circuit = build_voltage_divider()

    circuit.simulate(".OP", inplace=True)

    assert circuit.G.nodes["vin"]["solved_voltage"] == 10.0
    assert circuit.G.nodes["vout"]["solved_voltage"] == 5.0
    assert "solved_voltage" not in circuit.G.nodes["gnd"]


def test_simulate_inplace_ignores_non_voltage_and_hidden_columns(build_voltage_divider, stub_xyce_execution):
    waveforms = pd.DataFrame(
        {
            "TIME": [0.0],
            "V(N_1)": [10.0],
            "V(_INT_N_1_N_2_0_step1)": [7.5],
            "I(V_SRC)": [0.1],
        }
    )
    stub_xyce_execution(waveforms=waveforms)
    circuit = build_voltage_divider()

    circuit.simulate(".OP", inplace=True)

    assert circuit.G.nodes["vin"]["solved_voltage"] == 10.0
    assert "solved_voltage" not in circuit.G.nodes["vout"]


def test_simulate_inplace_rejects_multirow_waveforms(build_transient_graph, stub_xyce_execution):
    stub_xyce_execution(
        waveforms=pd.DataFrame({"TIME": [0.0, 1.0], "V(N_1)": [0.0, 1.0], "V(N_2)": [0.0, 0.5]})
    )
    circuit = build_transient_graph()

    with pytest.raises(ValueError, match="Cannot use inplace=True with multi-point sweeps."):
        circuit.simulate(".TRAN 1u 10u", inplace=True)


def test_simulate_returns_original_graph_snapshot_before_inplace_updates(
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP", inplace=True)

    assert "solved_voltage" not in result.original_graph.nodes["vin"]
    assert "solved_voltage" not in result.original_graph.nodes["vout"]
    assert circuit.G.nodes["vin"]["solved_voltage"] == 10.0


def test_simulate_returns_expanded_graph_independent_from_circuit_graph(
    build_voltage_divider,
    stub_xyce_execution,
):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")
    result.expanded_graph.add_node("result_only")

    assert "result_only" not in circuit.G


def test_simulate_returns_copied_node_map_inverse(monkeypatch, build_voltage_divider, stub_xyce_execution):
    class TrackingCompiler(graph_module.NetlistCompiler):
        last_instance = None

        def __init__(self, graph, global_directives):
            super().__init__(graph, global_directives)
            TrackingCompiler.last_instance = self

    monkeypatch.setattr(graph_module, "NetlistCompiler", TrackingCompiler)
    stub_xyce_execution()
    circuit = build_voltage_divider()

    result = circuit.simulate(".OP")
    compiler_instance = TrackingCompiler.last_instance
    result.node_map_inverse["N_1"] = "changed"

    assert compiler_instance is not None
    assert result.node_map_inverse is not compiler_instance.node_map_inverse
    assert compiler_instance.node_map_inverse["N_1"] == "vin"


def test_simulate_rejects_too_many_deprecated_positional_arguments(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(TypeError, match="simulate\\(\\) accepts at most two deprecated positional arguments."):
        circuit.simulate("OP", ".OP", ["V(N_1)"], ["V(N_2)"])


def test_simulate_rejects_legacy_analysis_mismatch(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(ValueError, match="analysis_cmd must start with '.OP'."):
        circuit.simulate("OP", ".TRAN 1u 1u")


def test_simulate_rejects_duplicate_legacy_print_vars(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()

    with pytest.raises(TypeError, match="print_vars must be passed once."):
        circuit.simulate("OP", ".OP", ["V(N_1)"], print_vars=["V(N_2)"])


def test_simulate_inplace_rejects_existing_solved_voltage(build_voltage_divider, stub_xyce_execution):
    stub_xyce_execution()
    circuit = build_voltage_divider()
    circuit.G.nodes["vin"]["solved_voltage"] = 99.0

    with pytest.raises(RuntimeError, match="Attribute 'solved_voltage' already exists on node."):
        circuit.simulate(".OP", inplace=True)


def test_simulate_op_raises_when_no_non_ground_user_nodes_are_available(stub_xyce_execution, tmp_path):
    stub_xyce_execution()
    circuit = CircuitGraph(xyce_path="Xyce", base_out_dir=str(tmp_path))
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("gnd", "gnd", [VoltageSource("src", 0.0)])

    with pytest.raises(ValueError, match="No non-ground user nodes available for default print_vars."):
        circuit.simulate(".OP")


def test_simulate_transient_wrapper_includes_nonzero_start_offset(build_transient_graph, stub_xyce_execution):
    stub_xyce_execution(
        waveforms=pd.DataFrame({"TIME": [0.0, 1.0], "V(N_1)": [0.0, 1.0], "V(N_2)": [0.0, 0.5]})
    )
    circuit = build_transient_graph()

    result = circuit.simulate_transient("1u", "10u", start="2u")

    assert ".TRAN 1u 10u 2u" in result.netlist


def test_simulate_wrappers_validate_string_inputs(build_voltage_divider, build_transient_graph, stub_xyce_execution):
    stub_xyce_execution()

    with pytest.raises(TypeError, match="step must be a string."):
        build_transient_graph().simulate_transient(1, "10u")

    with pytest.raises(TypeError, match="sweep_type must be a string."):
        build_voltage_divider().simulate_ac(10, "5", "1", "1e3")

    with pytest.raises(TypeError, match="source_name must be a string."):
        build_voltage_divider().simulate_dc(1, "0", "10", "1")
