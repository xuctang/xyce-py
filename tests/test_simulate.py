from __future__ import annotations

import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Resistor, VoltageSource


def _xyce_available() -> bool:
    return Path("/usr/local/XyceNF_7.10/bin/Xyce").exists() or shutil.which("Xyce") is not None


@unittest.skipUnless(_xyce_available(), "Xyce is not available in this environment.")
class CircuitGraphSimulateTests(unittest.TestCase):
    def _build_voltage_divider(self, base_out_dir: str) -> CircuitGraph:
        graph = CircuitGraph(base_out_dir=base_out_dir)
        graph.add_node("gnd", is_ground=True)
        graph.add_node("vin")
        graph.add_node("vout")
        graph.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
        graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
        graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])
        return graph

    def _build_multi_element_graph(self, base_out_dir: str) -> CircuitGraph:
        graph = CircuitGraph(base_out_dir=base_out_dir)
        graph.add_node("gnd", is_ground=True)
        graph.add_node("vin")
        graph.add_node("vout")
        graph.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
        graph.add_branch("vin", "vout", [Resistor("r1", 1000), Resistor("r2", 1000)])
        graph.add_branch("vout", "gnd", [Resistor("load", 1000)])
        return graph

    def _build_transient_graph(self, base_out_dir: str) -> CircuitGraph:
        graph = CircuitGraph(base_out_dir=base_out_dir)
        graph.add_node("gnd", is_ground=True)
        graph.add_node("vin")
        graph.add_node("vout")
        graph.add_branch(
            "vin",
            "gnd",
            [VoltageSource("pulse", 0.0, "PULSE(0 1 0 1u 1u 5u 10u)")],
        )
        graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
        graph.add_branch("vout", "gnd", [Capacitor("c1", "1u")])
        return graph

    def test_op_simulation_defaults_to_all_non_ground_user_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)

            result = graph.simulate(".OP")

        self.assertEqual(len(result.waveforms), 1)
        self.assertEqual(list(result.waveforms.columns), ["V(N_1)", "V(N_2)"])
        self.assertEqual(result.node_map_inverse, {"0": "gnd", "N_1": "vin", "N_2": "vout"})

    def test_op_simulation_with_custom_print_vars_preserves_requested_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)

            result = graph.simulate(".OP", print_vars=["V(N_2)"])

        self.assertEqual(list(result.waveforms.columns), ["V(N_2)"])
        self.assertIn(".OP", result.netlist)
        self.assertIn(".PRINT DC FORMAT=CSV FILE=output.csv V(N_2)", result.netlist)
        self.assertNotIn(".PRINT OP", result.netlist)
        self.assertTrue(result.netlist.endswith(".END\n"))
        self.assertEqual(list(result.translated_waveforms().columns), ["V(vout)"])

    def test_simulate_returns_expanded_graph_for_multi_element_branches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_multi_element_graph(tmpdir)

            result = graph.simulate(".OP")

        hidden_nodes = [
            node for node, data in result.expanded_graph.nodes(data=True) if data.get("is_hidden")
        ]
        self.assertEqual(hidden_nodes, ["_INT_N_1_N_2_0_step1"])

    def test_inplace_op_writes_solved_voltage_and_preserves_original_graph_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)

            result = graph.simulate(".OP", inplace=True)

        self.assertNotIn("solved_voltage", result.original_graph.nodes["vin"])
        self.assertNotIn("solved_voltage", result.original_graph.nodes["vout"])
        self.assertIn("solved_voltage", graph.G.nodes["vin"])
        self.assertIn("solved_voltage", graph.G.nodes["vout"])
        self.assertAlmostEqual(graph.G.nodes["vin"]["solved_voltage"], 10.0, places=6)
        self.assertAlmostEqual(graph.G.nodes["vout"]["solved_voltage"], 5.0, places=6)

    def test_inplace_raises_when_solved_voltage_already_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)
            graph.G.nodes["vout"]["solved_voltage"] = 1.23

            with self.assertRaisesRegex(
                RuntimeError,
                "Attribute 'solved_voltage' already exists on node. Use inplace=False.",
            ):
                graph.simulate(".OP", inplace=True)

    def test_inplace_raises_for_multi_point_transient_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_transient_graph(tmpdir)

            with self.assertRaisesRegex(
                ValueError,
                "Cannot use inplace=True with multi-point sweeps. Extract data from SolveResult.waveforms instead.",
            ):
                graph.simulate(".TRAN 1u 20u", inplace=True)

    def test_deprecated_two_string_simulate_form_still_works(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = graph.simulate("OP", ".OP")

        self.assertEqual(len(result.waveforms), 1)
        self.assertTrue(any(item.category is DeprecationWarning for item in caught))

    def test_simulate_op_wrapper_matches_generic_op(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_voltage_divider(tmpdir)

            result = graph.simulate_op()

        self.assertIn(".OP", result.netlist)
        self.assertIn(".PRINT DC FORMAT=CSV FILE=output.csv", result.netlist)

    def test_simulate_transient_wrapper_builds_tran_directive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = self._build_transient_graph(tmpdir)

            result = graph.simulate_transient("1u", "20u")

        self.assertIn(".TRAN 1u 20u", result.netlist)
        self.assertIn(".PRINT TRAN FORMAT=CSV FILE=output.csv", result.netlist)
        translated = result.translated_waveforms()
        self.assertIn("V(vin)", translated.columns)
        self.assertIn("V(vout)", translated.columns)
        self.assertEqual(result.waveforms.columns[0], "TIME")


if __name__ == "__main__":
    unittest.main()
