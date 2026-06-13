from __future__ import annotations

from dataclasses import asdict

import networkx as nx
import pandas as pd
import pytest

from xyce_py.models import (
    BJT,
    MOSFET,
    BehavioralSource,
    Capacitor,
    CurrentSource,
    Diode,
    Inductor,
    RawNTerminalDevice,
    RawTwoTerminalElement,
    Resistor,
    SolveResult,
    Subcircuit,
    VoltageSource,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        (Resistor("r1", 1), "R_r1 NP NN 1.0"),
        (Capacitor("c1", 2.5), "C_c1 NP NN 2.5"),
        (Inductor("l1", "3u"), "L_l1 NP NN 3u"),
        (VoltageSource("v1", -4), "V_v1 NP NN DC -4.0"),
        (CurrentSource("i1", 0.125), "I_i1 NP NN DC 0.125"),
        (Diode("d1", "DMOD"), "D_d1 NP NN DMOD"),
        (BehavioralSource("b1", "V(in) + 1", "V"), "B_b1 NP NN V={V(in) + 1}"),
    ],
)
def test_two_terminal_models_emit_exact_spice_prefixes_and_values(element, expected):
    assert element.to_spice("NP", "NN") == expected


@pytest.mark.parametrize(
    "element",
    [
        Resistor("r1", 1),
        Capacitor("c1", 1),
        Inductor("l1", 1),
        VoltageSource("v1", 1),
        CurrentSource("i1", 1),
        Diode("d1", "DMOD"),
        BehavioralSource("b1", "V(in)", "I"),
    ],
)
@pytest.mark.parametrize("bad_node", [None, 1, True, "", " \t "])
def test_two_terminal_models_reject_invalid_spice_node_names(element, bad_node):
    with pytest.raises((TypeError, ValueError)):
        element.to_spice(bad_node, "0")

    with pytest.raises((TypeError, ValueError)):
        element.to_spice("n1", bad_node)


@pytest.mark.parametrize("model_cls", [Resistor, Capacitor, Inductor])
@pytest.mark.parametrize("bad_value", [None, True, False, "", " \n "])
def test_passive_models_reject_invalid_value_like_inputs(model_cls, bad_value):
    with pytest.raises((TypeError, ValueError)):
        model_cls("x1", bad_value)


@pytest.mark.parametrize("source_cls", [VoltageSource, CurrentSource])
@pytest.mark.parametrize("bad_dc_value", [None, True, False, "1", object()])
def test_source_models_reject_non_numeric_dc_values(source_cls, bad_dc_value):
    with pytest.raises(TypeError):
        source_cls("src", bad_dc_value)


@pytest.mark.parametrize("source_cls", [VoltageSource, CurrentSource])
@pytest.mark.parametrize("bad_transient", ["", "   ", 3, True])
def test_source_models_reject_invalid_transient_expressions(source_cls, bad_transient):
    with pytest.raises((TypeError, ValueError)):
        source_cls("src", 1.0, bad_transient)


@pytest.mark.parametrize(
    ("device", "nodes", "expected"),
    [
        (BJT("q1", "QMOD"), ["c", "b", "e"], "Q_q1 c b e QMOD"),
        (MOSFET("m1", "NMOS"), ["d", "g", "s", "bulk"], "M_m1 d g s bulk NMOS"),
        (Subcircuit("u1", "AMP", 3), ["in", "out", "vdd"], "X_u1 in out vdd AMP"),
    ],
)
def test_multi_terminal_devices_emit_exact_spice_with_terminal_order(device, nodes, expected):
    assert device.to_spice(nodes) == expected


@pytest.mark.parametrize(
    ("device", "bad_nodes", "error_type"),
    [
        (BJT("q1", "QMOD"), ("c", "b", "e"), TypeError),
        (BJT("q1", "QMOD"), ["c", "b"], ValueError),
        (MOSFET("m1", "NMOS"), ["d", "g", "s"], ValueError),
        (MOSFET("m1", "NMOS"), ["d", "g", "s", ""], ValueError),
        (Subcircuit("u1", "AMP", 2), ["in", 3], TypeError),
    ],
)
def test_multi_terminal_devices_reject_invalid_mapped_nodes(device, bad_nodes, error_type):
    with pytest.raises(error_type):
        device.to_spice(bad_nodes)


@pytest.mark.parametrize("bad_model_name", [None, "", " \t "])
def test_device_model_names_must_be_non_empty_strings(bad_model_name):
    with pytest.raises((TypeError, ValueError)):
        BJT("q1", bad_model_name)

    with pytest.raises((TypeError, ValueError)):
        MOSFET("m1", bad_model_name)

    with pytest.raises((TypeError, ValueError)):
        Diode("d1", bad_model_name)


@pytest.mark.parametrize("bad_terminals", [None, True, False, 0, -1, 1.5, "2"])
def test_subcircuit_terminal_count_contract(bad_terminals):
    with pytest.raises((TypeError, ValueError)):
        Subcircuit("u1", "AMP", bad_terminals)


@pytest.mark.parametrize("source_type", ["", "v", "i", "P", "VI", 1])
def test_behavioral_source_accepts_only_exact_voltage_or_current_source_type(source_type):
    with pytest.raises((TypeError, ValueError)):
        BehavioralSource("b1", "V(in)", source_type)


def test_raw_two_terminal_element_reuses_spice_node_validation():
    element = RawTwoTerminalElement("raw", "R_$name $node_pos $node_neg 1k")

    with pytest.raises(TypeError, match="node_pos must be a string"):
        element.to_spice(1, "0")


def test_raw_n_terminal_device_reuses_terminal_arity_validation():
    device = RawNTerminalDevice(
        "raw",
        "MODEL",
        terminals=2,
        template="X_$name $n0 $n1 $model_name",
    )

    with pytest.raises(ValueError, match="exactly 2 node names"):
        device.to_spice(["N_1"])


@pytest.mark.parametrize("terminals", [0, -1, True, "2"])
def test_raw_n_terminal_device_rejects_invalid_terminal_counts(terminals):
    with pytest.raises((TypeError, ValueError)):
        RawNTerminalDevice("raw", "MODEL", terminals=terminals, template="X_$name $n0 $model_name")


def test_to_spice_calls_do_not_mutate_model_dataclass_state():
    models = [
        Resistor("r1", "1k"),
        Capacitor("c1", "1u"),
        Inductor("l1", "1m"),
        VoltageSource("v1", 5, "PULSE(0 5 0 1n 1n 5n 10n)"),
        CurrentSource("i1", -1, "SIN(0 1 1k)"),
        Diode("d1", "DMOD"),
        BehavioralSource("b1", "V(in)", "V"),
    ]
    before = [asdict(model) for model in models]

    for model in models:
        model.to_spice("n1", "0")

    assert [asdict(model) for model in models] == before


def test_translated_waveforms_preserves_data_and_original_frame_after_data_mutation():
    original = pd.DataFrame({"V(N_1)": [1.0], "TIME": [0.0]})
    result = SolveResult(
        original_graph=nx.MultiDiGraph(),
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=original,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vin"},
    )

    translated = result.translated_waveforms()
    translated.loc[0, "V(vin)"] = 99.0

    assert original.loc[0, "V(N_1)"] == 1.0
    assert list(original.columns) == ["V(N_1)", "TIME"]


def test_translated_waveforms_handles_non_string_and_duplicate_columns():
    original = pd.DataFrame([[1.0, 2.0, 3.0]], columns=["V(N_1)", "V(N_1)", 7])
    result = SolveResult(
        original_graph=nx.MultiDiGraph(),
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=original,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vin"},
    )

    translated = result.translated_waveforms()

    assert list(translated.columns) == ["V(vin)", "V(vin)", 7]
    assert list(original.columns) == ["V(N_1)", "V(N_1)", 7]
