from __future__ import annotations

import unittest

import networkx as nx

from xyce_py.graph import CircuitGraph, CircuitTopologyError
from xyce_py.models import BJT, MOSFET, Resistor


class CircuitGraphTests(unittest.TestCase):
    def test_initialization_creates_empty_graph_and_directives(self):
        graph = CircuitGraph()

        self.assertIsInstance(graph.G, nx.MultiDiGraph)
        self.assertEqual(len(graph.G.nodes), 0)
        self.assertEqual(len(graph.G.edges), 0)
        self.assertEqual(graph.global_directives, [])

    def test_add_node_adds_regular_node(self):
        graph = CircuitGraph()

        graph.add_node("n1")

        self.assertIn("n1", graph.G)
        self.assertNotIn("is_ground", graph.G.nodes["n1"])

    def test_add_node_marks_ground(self):
        graph = CircuitGraph()

        graph.add_node("0", is_ground=True)

        self.assertTrue(graph.G.nodes["0"]["is_ground"])

    def test_add_node_allows_idempotent_ground_readd(self):
        graph = CircuitGraph()

        graph.add_node("0", is_ground=True)
        graph.add_node("0", is_ground=True)

        self.assertTrue(graph.G.nodes["0"]["is_ground"])
        self.assertEqual(
            [node for node, data in graph.G.nodes(data=True) if data.get("is_ground")],
            ["0"],
        )

    def test_add_node_rejects_second_distinct_ground(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)

        with self.assertRaises(ValueError):
            graph.add_node("gnd", is_ground=True)

    def test_add_branch_stores_elements_on_edge(self):
        graph = CircuitGraph()
        graph.add_node("n1")
        graph.add_node("n2")
        elements = [Resistor("r1", 1000)]

        graph.add_branch("n1", "n2", elements)

        edge_data = list(graph.G.edges(keys=True, data=True))
        self.assertEqual(len(edge_data), 1)
        self.assertEqual(edge_data[0][0], "n1")
        self.assertEqual(edge_data[0][1], "n2")
        self.assertIs(edge_data[0][3]["elements"], elements)

    def test_add_branch_allows_parallel_edges(self):
        graph = CircuitGraph()
        graph.add_node("n1")
        graph.add_node("n2")

        graph.add_branch("n1", "n2", [Resistor("r1", 1000)])
        graph.add_branch("n1", "n2", [Resistor("r2", 2000)])

        edges = list(graph.G.edges(keys=True, data=True))
        self.assertEqual(len(edges), 2)
        self.assertNotEqual(edges[0][2], edges[1][2])

    def test_add_branch_auto_creates_missing_nodes(self):
        graph = CircuitGraph()
        graph.add_branch("n1", "n2", [Resistor("r1", 1000)])

        self.assertIn("n1", graph.G)
        self.assertIn("n2", graph.G)
        self.assertEqual(len(list(graph.G.edges(keys=True))), 1)

    def test_add_branch_auto_created_nodes_are_not_ground(self):
        graph = CircuitGraph()

        graph.add_branch("n1", "n2", [Resistor("r1", 1000)])

        self.assertNotIn("is_ground", graph.G.nodes["n1"])
        self.assertNotIn("is_ground", graph.G.nodes["n2"])

    def test_add_branch_rejects_empty_elements(self):
        graph = CircuitGraph()
        graph.add_node("n1")
        graph.add_node("n2")

        with self.assertRaises(ValueError):
            graph.add_branch("n1", "n2", [])

    def test_add_branch_rejects_non_list_elements(self):
        graph = CircuitGraph()
        graph.add_node("n1")
        graph.add_node("n2")

        with self.assertRaises(TypeError):
            graph.add_branch("n1", "n2", (Resistor("r1", 1000),))

    def test_add_branch_rejects_non_circuit_element_entries(self):
        graph = CircuitGraph()
        graph.add_node("n1")
        graph.add_node("n2")

        with self.assertRaises(TypeError):
            graph.add_branch("n1", "n2", [Resistor("r1", 1000), "not-an-element"])

    def test_add_device_stores_hidden_device_node_and_links(self):
        graph = CircuitGraph()
        device = BJT("amp", "QMOD")
        nodes = ["collector", "base", "emitter"]

        graph.add_device(device, nodes)

        device_node_id = "_DEV_amp"
        self.assertIn(device_node_id, graph.G)
        self.assertEqual(
            graph.G.nodes[device_node_id],
            {
                "is_device": True,
                "device_obj": device,
                "ordered_nodes": nodes,
            },
        )

        edges = list(graph.G.edges(keys=True, data=True))
        self.assertEqual(len(edges), 3)
        self.assertEqual({edge[1] for edge in edges}, set(nodes))
        self.assertTrue(all(edge[0] == device_node_id for edge in edges))
        self.assertTrue(all(edge[3] == {"is_device_link": True} for edge in edges))

    def test_add_device_auto_creates_missing_nodes(self):
        graph = CircuitGraph()

        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "emitter"])

        self.assertIn("collector", graph.G)
        self.assertIn("base", graph.G)
        self.assertIn("emitter", graph.G)
        self.assertNotIn("is_ground", graph.G.nodes["collector"])

    def test_add_device_rejects_wrong_terminal_count(self):
        graph = CircuitGraph()

        with self.assertRaises(ValueError):
            graph.add_device(MOSFET("sw", "NMOS"), ["drain", "gate", "source"])

    def test_add_device_rejects_non_list_nodes(self):
        graph = CircuitGraph()

        with self.assertRaises(TypeError):
            graph.add_device(BJT("amp", "QMOD"), ("collector", "base", "emitter"))

    def test_add_device_rejects_non_device_input(self):
        graph = CircuitGraph()

        with self.assertRaises(TypeError):
            graph.add_device(Resistor("r1", 1000), ["n1", "n2"])

    def test_add_device_rejects_duplicate_device_name_collision(self):
        graph = CircuitGraph()
        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "emitter"])

        with self.assertRaises(ValueError):
            graph.add_device(BJT("amp", "QMOD2"), ["c2", "b2", "e2"])

    def test_add_device_rejects_collision_with_existing_user_node(self):
        graph = CircuitGraph()
        graph.add_node("_DEV_amp")

        with self.assertRaises(ValueError):
            graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "emitter"])

    def test_add_model_appends_valid_directive(self):
        graph = CircuitGraph()

        graph.add_model(".MODEL DFAST D(IS=1e-9)")

        self.assertEqual(graph.global_directives, [".MODEL DFAST D(IS=1e-9)"])

    def test_add_options_appends_valid_directive(self):
        graph = CircuitGraph()

        graph.add_options(".OPTIONS DEVICE GMIN=1e-8")

        self.assertEqual(graph.global_directives, [".OPTIONS DEVICE GMIN=1e-8"])

    def test_add_subcircuit_appends_valid_directive(self):
        graph = CircuitGraph()
        subckt = ".SUBCKT OPAMP INP INN VDD VSS OUT\nR1 OUT INP 1k\n.ENDS"

        graph.add_subcircuit(subckt)

        self.assertEqual(graph.global_directives, [subckt])

    def test_directives_preserve_insertion_order(self):
        graph = CircuitGraph()
        subckt = ".SUBCKT BUF IN OUT\nE1 OUT 0 IN 0 1\n.ENDS"

        graph.add_model(".MODEL DFAST D(IS=1e-9)")
        graph.add_subcircuit(subckt)
        graph.add_options(".OPTIONS DEVICE GMIN=1e-8")

        self.assertEqual(
            graph.global_directives,
            [".MODEL DFAST D(IS=1e-9)", subckt, ".OPTIONS DEVICE GMIN=1e-8"],
        )

    def test_add_model_rejects_invalid_or_empty_strings(self):
        graph = CircuitGraph()

        with self.assertRaises(ValueError):
            graph.add_model("")

        with self.assertRaises(ValueError):
            graph.add_model(".OPTIONS DEVICE GMIN=1e-8")

    def test_add_options_rejects_invalid_or_empty_strings(self):
        graph = CircuitGraph()

        with self.assertRaises(ValueError):
            graph.add_options("")

        with self.assertRaises(ValueError):
            graph.add_options(".MODEL DFAST D(IS=1e-9)")

    def test_add_subcircuit_rejects_invalid_or_empty_strings(self):
        graph = CircuitGraph()

        with self.assertRaises(ValueError):
            graph.add_subcircuit("")

        with self.assertRaises(ValueError):
            graph.add_subcircuit(".SUBCKT OPAMP INP INN OUT")

        with self.assertRaises(ValueError):
            graph.add_subcircuit("R1 OUT IN 1k\n.ENDS")

    def test_validate_topology_accepts_single_grounded_component(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_node("n2")
        graph.add_branch("0", "n1", [Resistor("r1", 1000)])
        graph.add_branch("n1", "n2", [Resistor("r2", 2000)])

        graph._validate_topology()

    def test_validate_topology_rejects_missing_ground(self):
        graph = CircuitGraph()
        graph.add_node("n1")

        with self.assertRaisesRegex(CircuitTopologyError, "Circuit has no ground reference."):
            graph._validate_topology()

    def test_validate_topology_rejects_multiple_ground_nodes(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("gnd")
        graph.G.nodes["gnd"]["is_ground"] = True

        with self.assertRaisesRegex(CircuitTopologyError, "Circuit has multiple ground references."):
            graph._validate_topology()

    def test_validate_topology_rejects_disconnected_component_without_ground(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_node("float1")
        graph.add_node("float2")
        graph.add_branch("0", "n1", [Resistor("r1", 1000)])
        graph.add_branch("float1", "float2", [Resistor("r2", 2000)])

        with self.assertRaisesRegex(
            CircuitTopologyError,
            "Floating subgraph detected with no path to ground.",
        ):
            graph._validate_topology()

    def test_validate_topology_accepts_ground_only_graph(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)

        graph._validate_topology()

    def test_validate_topology_accepts_component_connected_through_device_node(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_branch("emitter", "0", [Resistor("re", 1000)])
        graph.add_device(BJT("amp", "QMOD"), ["collector", "base", "emitter"])

        graph._validate_topology()

    def test_validate_topology_rejects_connected_floating_subgraph(self):
        graph = CircuitGraph()
        graph.add_node("0", is_ground=True)
        graph.add_node("n1")
        graph.add_node("float1")
        graph.add_node("float2")
        graph.add_node("float3")
        graph.add_branch("0", "n1", [Resistor("r1", 1000)])
        graph.add_branch("float1", "float2", [Resistor("r2", 2000)])
        graph.add_branch("float2", "float3", [Resistor("r3", 3000)])

        with self.assertRaisesRegex(
            CircuitTopologyError,
            "Floating subgraph detected with no path to ground.",
        ):
            graph._validate_topology()


if __name__ == "__main__":
    unittest.main()
