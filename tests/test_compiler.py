from __future__ import annotations

import unittest

from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph, CircuitTopologyError
from xyce_py.models import BJT, Capacitor, Inductor, Resistor, Subcircuit


class NetlistCompilerTests(unittest.TestCase):
    def test_compile_sanitizes_user_nodes_and_round_trips_maps(self):
        graph = CircuitGraph()
        graph.add_node("gnd", is_ground=True)
        graph.add_node("input")
        graph.add_node("output")
        graph.add_branch("input", "output", [Resistor("r1", 1000)])
        graph.add_branch("output", "gnd", [Resistor("r2", 2000)])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        compiler.compile()

        self.assertEqual(compiler.node_map_forward["gnd"], "0")
        self.assertEqual(compiler.node_map_forward["input"], "N_1")
        self.assertEqual(compiler.node_map_forward["output"], "N_2")
        self.assertEqual(compiler.node_map_inverse["0"], "gnd")
        self.assertEqual(compiler.node_map_inverse["N_1"], "input")
        self.assertEqual(compiler.node_map_inverse["N_2"], "output")

    def test_compile_skips_device_nodes_when_building_node_maps(self):
        graph = CircuitGraph()
        graph.add_node("gnd", is_ground=True)
        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "gnd"])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        compiler.compile()

        self.assertEqual(compiler.node_map_forward["gnd"], "0")
        self.assertEqual(compiler.node_map_forward["collector"], "N_1")
        self.assertEqual(compiler.node_map_forward["base"], "N_2")
        self.assertNotIn("_DEV_amp", compiler.node_map_forward)
        self.assertNotIn("_DEV_amp", compiler.node_map_inverse.values())

    def test_compile_emits_single_element_branch_line_and_preserves_expanded_graph_shape(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_branch("n1", "0", [Resistor("load", 1000)])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn("R_load N_1 0 1000.0", netlist)
        self.assertEqual(list(graph.G.edges(keys=True)), list(compiler.expanded_graph.edges(keys=True)))

    def test_compile_expands_two_element_branch_with_one_hidden_node(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_branch("n1", "0", [Resistor("r1", 1000), Capacitor("c1", "10u")])

        graph._validate_topology()
        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]
        self.assertEqual(len(hidden_nodes), 1)
        hidden = hidden_nodes[0]
        self.assertEqual(hidden, "_INT_N_1_0_0_step1")
        self.assertNotIn(("n1", "0", 0), list(compiler.expanded_graph.edges(keys=True)))
        self.assertIn(("n1", hidden, 0), list(compiler.expanded_graph.edges(keys=True)))
        self.assertIn((hidden, "0", 0), list(compiler.expanded_graph.edges(keys=True)))
        self.assertIn("R_r1 N_1 _INT_N_1_0_0_step1 1000.0", netlist)
        self.assertIn("C_c1 _INT_N_1_0_0_step1 0 10u", netlist)

    def test_compile_expands_three_element_branch_with_two_hidden_nodes(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_branch(
            "n1",
            "0",
            [Resistor("r1", 1000), Capacitor("c1", "10u"), Inductor("l1", 0.002)],
        )

        graph._validate_topology()
        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        hidden_nodes = [node for node, data in compiler.expanded_graph.nodes(data=True) if data.get("is_hidden")]
        self.assertEqual(hidden_nodes, ["_INT_N_1_0_0_step1", "_INT_N_1_0_0_step2"])
        edges = list(compiler.expanded_graph.edges(keys=True, data=True))
        self.assertEqual(len(edges), 3)
        self.assertTrue(all(len(edge[3]["elements"]) == 1 for edge in edges))
        self.assertIn("R_r1 N_1 _INT_N_1_0_0_step1 1000.0", netlist)
        self.assertIn("C_c1 _INT_N_1_0_0_step1 _INT_N_1_0_0_step2 10u", netlist)
        self.assertIn("L_l1 _INT_N_1_0_0_step2 0 0.002", netlist)

    def test_compile_assembles_directives_default_gmin_and_end(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_model(".MODEL DFAST D(IS=1e-9)")
        graph.add_options(".OPTIONS NONLIN RELTOL=1e-4")
        graph.add_branch("n1", "0", [Resistor("load", 1000)])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        expected_lines = netlist.splitlines()
        self.assertEqual(expected_lines[0], "* Generated Circuit")
        self.assertEqual(expected_lines[1], ".MODEL DFAST D(IS=1e-9)")
        self.assertEqual(expected_lines[2], ".OPTIONS NONLIN RELTOL=1e-4")
        self.assertEqual(expected_lines[3], ".OPTIONS DEVICE GMIN=1e-8")
        self.assertEqual(expected_lines[-1], ".END")
        self.assertEqual(netlist.count(".OPTIONS DEVICE GMIN=1e-8"), 1)

    def test_compile_emits_bjt_device_line_and_skips_device_link_edges(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "0"])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn("Q_amp N_1 N_2 0 QMOD", netlist)
        self.assertNotIn("is_device_link", netlist)
        self.assertEqual(list(compiler.expanded_graph.edges(keys=True)), list(graph.G.edges(keys=True)))

    def test_compile_emits_subcircuit_device_line_using_ordered_nodes(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_device(Subcircuit("u1", "OPAMP", terminals=5), ["inp", "inn", "vdd", "0", "out"])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn("X_u1 N_1 N_2 N_3 0 N_4 OPAMP", netlist)

    def test_compile_does_not_parse_subcircuit_definition_arity(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_subcircuit(".SUBCKT MY_AMP IN OUT\n.ENDS")
        graph.add_device(Subcircuit("u1", "MY_AMP", terminals=3), ["inp", "out", "0"])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn(".SUBCKT MY_AMP IN OUT", netlist)
        self.assertIn("X_u1 N_1 N_2 0 MY_AMP", netlist)

    def test_compile_mixed_circuit_emits_branch_and_device_lines(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_branch("collector", "0", [Resistor("load", 1000)])
        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "0"])

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn("R_load N_1 0 1000.0", netlist)
        self.assertIn("Q_amp N_1 N_2 0 QMOD", netlist)

    def test_compile_does_not_own_topology_validation_for_missing_ground(self):
        graph = CircuitGraph()
        graph.add_node("n1")

        compiler = NetlistCompiler(graph.G, graph.global_directives)
        netlist = compiler.compile()

        self.assertIn("R_", netlist) if False else self.assertEqual(
            netlist,
            "* Generated Circuit\n.OPTIONS DEVICE GMIN=1e-8\n.END\n",
        )

    def test_compile_does_not_own_topology_validation_for_floating_disconnected_component(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_node("float1")
        graph.add_node("float2")
        graph.add_branch("0", "n1", [Resistor("r1", 1000)])
        graph.add_branch("float1", "float2", [Resistor("r2", 2000)])

        compiler = NetlistCompiler(graph.G, graph.global_directives)

        netlist = compiler.compile()
        self.assertIn("R_r1 0 N_1 1000.0", netlist)
        self.assertIn("R_r2 N_2 N_3 2000.0", netlist)


if __name__ == "__main__":
    unittest.main()
