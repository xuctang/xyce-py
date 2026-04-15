from __future__ import annotations

import unittest

import networkx as nx
import pandas as pd

from xyce_py.models import (
    BehavioralSource,
    BJT,
    Capacitor,
    CurrentSource,
    Diode,
    Inductor,
    MOSFET,
    NTerminalDevice,
    Resistor,
    SolveResult,
    Subcircuit,
    VoltageSource,
)


class CircuitElementModelTests(unittest.TestCase):
    def test_passive_and_diode_to_spice_formats(self):
        cases = [
            (Resistor("load", 1000), ("n1", "0"), "R_load n1 0 1000.0"),
            (Capacitor("filter", "10u"), ("n1", "0"), "C_filter n1 0 10u"),
            (Inductor("choke", 0.002), ("n1", "0"), "L_choke n1 0 0.002"),
            (Diode("rect", "DFAST"), ("anode", "cathode"), "D_rect anode cathode DFAST"),
        ]
        for element, nodes, expected in cases:
            with self.subTest(element=element):
                self.assertEqual(element.to_spice(*nodes), expected)

    def test_voltage_source_to_spice_with_dc_only(self):
        element = VoltageSource("supply", 5.0)
        self.assertEqual(element.to_spice("vin", "0"), "V_supply vin 0 DC 5.0")

    def test_voltage_source_to_spice_with_transient_expression(self):
        element = VoltageSource("pulse", 5.0, "PULSE(0 5 0 1n 1n 10n 20n)")
        self.assertEqual(
            element.to_spice("vin", "0"),
            "V_pulse vin 0 DC 5.0 PULSE(0 5 0 1n 1n 10n 20n)",
        )

    def test_current_source_to_spice_with_dc_only(self):
        element = CurrentSource("bias", 0.002)
        self.assertEqual(element.to_spice("iin", "0"), "I_bias iin 0 DC 0.002")

    def test_current_source_to_spice_with_transient_expression(self):
        element = CurrentSource("pulse", 0.5, "SIN(0 0.5 1k)")
        self.assertEqual(
            element.to_spice("iin", "0"),
            "I_pulse iin 0 DC 0.5 SIN(0 0.5 1k)",
        )

    def test_behavioral_source_to_spice_formats(self):
        cases = [
            (BehavioralSource("ctrl", "V(in)-V(ref)", "V"), "B_ctrl out 0 V={V(in)-V(ref)}"),
            (BehavioralSource("sink", "0.1 * V(out)", "I"), "B_sink out 0 I={0.1 * V(out)}"),
        ]
        for element, expected in cases:
            with self.subTest(element=element):
                self.assertEqual(element.to_spice("out", "0"), expected)

    def test_n_terminal_device_to_spice_formats(self):
        cases = [
            (
                BJT("amp", "QMOD"),
                ["collector", "base", "emitter"],
                "Q_amp collector base emitter QMOD",
            ),
            (
                MOSFET("sw", "NMOS"),
                ["drain", "gate", "source", "bulk"],
                "M_sw drain gate source bulk NMOS",
            ),
            (
                Subcircuit("filter", "LOWPASS", terminals=5),
                ["n1", "n2", "n3", "n4", "n5"],
                "X_filter n1 n2 n3 n4 n5 LOWPASS",
            ),
        ]
        for element, nodes, expected in cases:
            with self.subTest(element=element):
                self.assertEqual(element.to_spice(nodes), expected)

    def test_n_terminal_device_expected_terminals(self):
        cases = [
            (BJT("amp", "QMOD"), 3),
            (MOSFET("sw", "NMOS"), 4),
            (Subcircuit("filter", "LOWPASS", terminals=5), 5),
        ]
        for element, expected in cases:
            with self.subTest(element=element):
                self.assertEqual(element.expected_terminals, expected)

    def test_n_terminal_device_base_class_is_abstract(self):
        with self.assertRaises(TypeError):
            NTerminalDevice("x1", "MODEL")

    def test_element_validation_rejects_malformed_inputs(self):
        cases = [
            (lambda: Resistor("", 1000), ValueError),
            (lambda: Resistor("r1", ""), ValueError),
            (lambda: Resistor("r1", None), TypeError),
            (lambda: Diode("d1", ""), ValueError),
            (lambda: BehavioralSource("b1", "", "V"), ValueError),
            (lambda: BehavioralSource("b1", "V(n1)", "X"), ValueError),
            (lambda: VoltageSource("v1", 1.0, ""), ValueError),
            (lambda: CurrentSource("i1", "1m"), TypeError),
            (lambda: BJT("", "QMOD"), ValueError),
            (lambda: MOSFET("m1", ""), ValueError),
            (lambda: Subcircuit("x1", "SUBCKT", terminals=0), ValueError),
            (lambda: Subcircuit("x1", "SUBCKT", terminals=-1), ValueError),
            (lambda: Subcircuit("x1", "SUBCKT", terminals=1.5), TypeError),
            (lambda: Subcircuit("x1", "SUBCKT", terminals=True), TypeError),
        ]
        for factory, error_type in cases:
            with self.subTest(factory=factory, error_type=error_type):
                with self.assertRaises(error_type):
                    factory()

    def test_to_spice_rejects_empty_nodes(self):
        element = Resistor("load", 1000)
        with self.assertRaises(ValueError):
            element.to_spice("", "0")

    def test_n_terminal_device_to_spice_rejects_wrong_terminal_count(self):
        cases = [
            (BJT("amp", "QMOD"), ["collector", "base"]),
            (MOSFET("sw", "NMOS"), ["drain", "gate", "source"]),
            (Subcircuit("filter", "LOWPASS", terminals=3), ["n1", "n2"]),
        ]
        for element, nodes in cases:
            with self.subTest(element=element, nodes=nodes):
                with self.assertRaises(ValueError):
                    element.to_spice(nodes)

    def test_n_terminal_device_to_spice_rejects_non_list_or_invalid_nodes(self):
        cases = [
            (BJT("amp", "QMOD"), ("collector", "base", "emitter"), TypeError),
            (BJT("amp", "QMOD"), ["collector", "", "emitter"], ValueError),
            (MOSFET("sw", "NMOS"), ["drain", "gate", None, "bulk"], TypeError),
        ]
        for element, nodes, error_type in cases:
            with self.subTest(element=element, nodes=nodes, error_type=error_type):
                with self.assertRaises(error_type):
                    element.to_spice(nodes)

    def test_solve_result_accepts_expected_types_without_mutation(self):
        original_graph = nx.MultiDiGraph()
        original_graph.add_edge("n1", "n2", key="r1")
        expanded_graph = original_graph.copy()
        expanded_graph.add_node("_hidden_series_1")
        waveforms = pd.DataFrame({"V(N1)": [1.0], "V(N2)": [0.5]})

        result = SolveResult(
            original_graph=original_graph,
            expanded_graph=expanded_graph,
            netlist="* netlist\nR_load n1 n2 1000\n.END\n",
            waveforms=waveforms,
            solve_time_sec=0.123,
            stdout="solver output",
            node_map_inverse={"N_1": "n1", "N_2": "n2"},
        )

        self.assertIs(result.original_graph, original_graph)
        self.assertIs(result.expanded_graph, expanded_graph)
        self.assertIs(result.waveforms, waveforms)
        self.assertTrue(result.netlist.startswith("* netlist"))
        self.assertEqual(result.solve_time_sec, 0.123)
        self.assertEqual(result.stdout, "solver output")
        self.assertEqual(result.node_map_inverse, {"N_1": "n1", "N_2": "n2"})

    def test_solve_result_translated_waveforms_maps_voltage_columns_back_to_user_ids(self):
        waveforms = pd.DataFrame(
            {
                "TIME": [0.0],
                "V(N_1)": [1.0],
                "V(_INT_N_1_N_2_0_step1)": [0.5],
                "I(V_SRC)": [0.1],
            }
        )
        result = SolveResult(
            original_graph=nx.MultiDiGraph(),
            expanded_graph=nx.MultiDiGraph(),
            netlist="* netlist\n.END\n",
            waveforms=waveforms,
            solve_time_sec=0.0,
            stdout="",
            node_map_inverse={"N_1": "Main_Filter_Cap"},
        )

        translated = result.translated_waveforms()

        self.assertEqual(
            list(translated.columns),
            ["TIME", "V(Main_Filter_Cap)", "V(_INT_N_1_N_2_0_step1)", "I(V_SRC)"],
        )
        self.assertEqual(list(result.waveforms.columns), ["TIME", "V(N_1)", "V(_INT_N_1_N_2_0_step1)", "I(V_SRC)"])

    def test_solve_result_translated_waveforms_preserves_device_specific_output_columns(self):
        waveforms = pd.DataFrame(
            {
                "TIME": [0.0],
                "V(N_1)": [1.2],
                "IC(Q_amp)": [0.004],
                "IB(Q_amp)": [0.0001],
                "I(V_SRC)": [0.01],
            }
        )
        result = SolveResult(
            original_graph=nx.MultiDiGraph(),
            expanded_graph=nx.MultiDiGraph(),
            netlist="* netlist\n.END\n",
            waveforms=waveforms,
            solve_time_sec=0.0,
            stdout="",
            node_map_inverse={"N_1": "collector"},
        )

        translated = result.translated_waveforms()

        self.assertEqual(
            list(translated.columns),
            ["TIME", "V(collector)", "IC(Q_amp)", "IB(Q_amp)", "I(V_SRC)"],
        )
        self.assertEqual(
            list(result.waveforms.columns),
            ["TIME", "V(N_1)", "IC(Q_amp)", "IB(Q_amp)", "I(V_SRC)"],
        )


if __name__ == "__main__":
    unittest.main()
