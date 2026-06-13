from __future__ import annotations

from dataclasses import asdict

import networkx as nx
import pandas as pd
import pytest

from xyce_py.models import (
    BJT,
    BehavioralSource,
    Capacitor,
    CircuitElement,
    CurrentSource,
    Inductor,
    MOSFET,
    NTerminalDevice,
    RawNTerminalDevice,
    RawTwoTerminalElement,
    Resistor,
    Subcircuit,
    VoltageSource,
    Diode,
    SolveResult,
)


pytestmark = pytest.mark.unit


def test_resistor_value_like_formats_numeric_and_engineering_inputs():
    assert Resistor("r_int", 10).to_spice("n1", "0") == "R_r_int n1 0 10.0"
    assert Resistor("r_float", 10.5).to_spice("n1", "0") == "R_r_float n1 0 10.5"
    assert Resistor("r_eng", "10u").to_spice("n1", "0") == "R_r_eng n1 0 10u"


def test_capacitor_value_like_accepts_scientific_notation_strings_verbatim():
    capacitor = Capacitor("c1", "1e-9")

    assert capacitor.to_spice("n1", "0") == "C_c1 n1 0 1e-9"


def test_inductor_value_like_rejects_boolean_inputs():
    with pytest.raises(TypeError):
        Inductor("l1", True)


def test_passive_value_policy_for_zero_and_negative_values():
    assert Resistor("r_zero", 0).to_spice("n1", "0") == "R_r_zero n1 0 0.0"
    assert Capacitor("c_neg", -1.5).to_spice("n1", "0") == "C_c_neg n1 0 -1.5"


def test_passive_value_policy_for_extreme_magnitudes():
    assert Resistor("r_huge", 1e20).to_spice("n1", "0") == "R_r_huge n1 0 1e+20"
    assert Inductor("l_tiny", 1e-20).to_spice("n1", "0") == "L_l_tiny n1 0 1e-20"


def test_passive_value_string_whitespace_policy():
    assert Resistor("r_space", " 10u ").to_spice("n1", "0") == "R_r_space n1 0  10u "


def test_sources_preserve_transient_expressions_with_spaces():
    voltage = VoltageSource("pulse", 5.0, "PULSE(0 5 0 1n 1n 10n 20n)")
    current = CurrentSource("sine", -0.5, "SIN(0 0.5 1k)")

    assert voltage.to_spice("vin", "0") == "V_pulse vin 0 DC 5.0 PULSE(0 5 0 1n 1n 10n 20n)"
    assert current.to_spice("iin", "0") == "I_sine iin 0 DC -0.5 SIN(0 0.5 1k)"


def test_sources_reject_empty_transient_expression():
    with pytest.raises(ValueError):
        VoltageSource("v1", 1.0, "   ")


def test_sources_reject_boolean_dc_values():
    with pytest.raises(TypeError):
        VoltageSource("v_bool", True)
    with pytest.raises(TypeError):
        CurrentSource("i_bool", False)


def test_behavioral_source_supports_parentheses_braces_and_nested_functions():
    source = BehavioralSource(
        "b1",
        "LIMIT(V(in), 0, 5) + IF(V(ctrl) > 1, SIN(V(out)), {GAIN})",
        "V",
    )

    assert (
        source.to_spice("out", "0")
        == "B_b1 out 0 V={LIMIT(V(in), 0, 5) + IF(V(ctrl) > 1, SIN(V(out)), {GAIN})}"
    )


def test_behavioral_source_rejects_lowercase_source_type():
    with pytest.raises(ValueError):
        BehavioralSource("b1", "V(in)", "v")


def test_bjt_terminal_order_is_preserved():
    transistor = BJT("amp", "QMOD")

    assert transistor.to_spice(["collector", "base", "emitter"]) == "Q_amp collector base emitter QMOD"


def test_mosfet_terminal_order_is_preserved():
    transistor = MOSFET("sw", "NMOS")

    assert (
        transistor.to_spice(["drain", "gate", "source", "bulk"])
        == "M_sw drain gate source bulk NMOS"
    )


def test_subcircuit_terminal_order_and_model_name_are_preserved():
    device = Subcircuit("u1", "LOWPASS_MODEL", terminals=4)

    assert device.to_spice(["n1", "n2", "n3", "n4"]) == "X_u1 n1 n2 n3 n4 LOWPASS_MODEL"


def test_raw_two_terminal_element_substitutes_name_and_spice_nodes():
    element = RawTwoTerminalElement("load", "R_$name $node_pos $node_neg {RLOAD}")

    assert element.to_spice("N_1", "0") == "R_load N_1 0 {RLOAD}"


def test_raw_n_terminal_device_substitutes_model_and_ordered_spice_nodes():
    device = RawNTerminalDevice(
        "xamp",
        "AMP_MODEL",
        terminals=3,
        template="X_$name $n0 $n1 $n2 $model_name",
    )

    assert device.expected_terminals == 3
    assert device.to_spice(["IN", "OUT", "0"]) == "X_xamp IN OUT 0 AMP_MODEL"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: RawTwoTerminalElement("bad", "R_$name $node_pos 0 1k"),
        lambda: RawTwoTerminalElement("bad", "R_$name $node_pos $missing 1k"),
        lambda: RawNTerminalDevice("bad", "MODEL", terminals=2, template="X_$name $n0 MODEL"),
        lambda: RawNTerminalDevice(
            "bad",
            "MODEL",
            terminals=2,
            template="X_$name $n0 $n1 $missing",
        ),
    ],
)
def test_raw_template_models_reject_invalid_templates(factory):
    with pytest.raises(ValueError):
        factory()


def test_to_spice_does_not_mutate_model_instances():
    voltage = VoltageSource("src", 5, "PULSE(0 5 0 1n 1n 5n 10n)")
    resistor = Resistor("r1", "1k")
    before_voltage = asdict(voltage)
    before_resistor = asdict(resistor)

    voltage.to_spice("vin", "0")
    resistor.to_spice("vin", "vout")

    assert asdict(voltage) == before_voltage
    assert asdict(resistor) == before_resistor


def test_model_validation_rejects_empty_strings_and_invalid_terminal_shapes():
    with pytest.raises(ValueError):
        Resistor("r1", "   ")

    with pytest.raises(TypeError):
        Diode("d1", None)

    with pytest.raises(TypeError):
        BJT("amp", "QMOD").to_spice(("collector", "base", "emitter"))

    with pytest.raises(ValueError):
        MOSFET("sw", "NMOS").to_spice(["d", "g", "s"])


def test_diode_formats_and_validates_model_name():
    diode = Diode("rect", "DMOD")

    assert diode.to_spice("anode", "cathode") == "D_rect anode cathode DMOD"

    with pytest.raises(ValueError):
        Diode("rect", "   ")


def test_subcircuit_rejects_invalid_terminal_count_values():
    with pytest.raises(TypeError):
        Subcircuit("u1", "AMP", terminals=True)

    with pytest.raises(ValueError):
        Subcircuit("u1", "AMP", terminals=0)


def test_translated_waveforms_leaves_unmapped_voltage_columns_unchanged():
    waveforms = pd.DataFrame({"V(N_1)": [1.0], "V(N_999)": [2.0]})
    result = SolveResult(
        original_graph=nx.MultiDiGraph(),
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=waveforms,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vin"},
    )

    translated = result.translated_waveforms()

    assert list(translated.columns) == ["V(vin)", "V(N_999)"]


def test_solved_graph_returns_copy_with_node_voltage_annotations():
    original_graph = nx.MultiDiGraph()
    original_graph.add_node("gnd", is_ground=True)
    original_graph.add_node("vin")
    original_graph.add_node("vout")
    waveforms = pd.DataFrame(
        {
            "V(N_1)": [10.0],
            "V(N_2)": [5.0],
            "V(0)": [0.0],
            "V(N_999)": [99.0],
            "I(V_supply)": [0.01],
        }
    )
    result = SolveResult(
        original_graph=original_graph,
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=waveforms,
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vin", "N_2": "vout", "0": "gnd"},
    )

    solved_graph = result.solved_graph()

    assert solved_graph is not original_graph
    assert solved_graph.nodes["vin"]["solved_voltage"] == 10.0
    assert solved_graph.nodes["vout"]["solved_voltage"] == 5.0
    assert "solved_voltage" not in solved_graph.nodes["gnd"]
    assert "solved_voltage" not in original_graph.nodes["vin"]


def test_solved_graph_uses_selected_waveform_row():
    original_graph = nx.MultiDiGraph()
    original_graph.add_node("vout")
    result = SolveResult(
        original_graph=original_graph,
        expanded_graph=nx.MultiDiGraph(),
        netlist="* test\n.END\n",
        waveforms=pd.DataFrame({"TIME": [0.0, 1.0], "V(N_1)": [1.0, 2.0]}),
        solve_time_sec=0.0,
        stdout="",
        spice_to_user_node={"N_1": "vout"},
    )

    solved_graph = result.solved_graph(row=1)

    assert solved_graph.nodes["vout"]["solved_voltage"] == 2.0


def test_abstract_base_classes_cannot_be_instantiated():
    with pytest.raises(TypeError):
        CircuitElement("x1")

    with pytest.raises(TypeError):
        NTerminalDevice("x1", "MODEL")
