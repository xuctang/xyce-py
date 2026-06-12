from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True)
class CompiledNetlistBody:
    lines: tuple[str, ...]
    node_map_forward: dict[object, str]
    node_map_inverse: dict[str, object]
    expanded_graph: nx.MultiDiGraph


class NetlistCompiler:
    def __init__(self, graph: nx.MultiDiGraph, global_directives: list[str]):
        self.graph = graph
        self.global_directives = global_directives
        self.node_map_forward: dict[object, str] = {}
        self.node_map_inverse: dict[str, object] = {}
        self.expanded_graph: nx.MultiDiGraph | None = None

    def compile(self) -> str:
        netlist_lines = list(self.compile_body().lines)
        netlist_lines.append(".END")
        return "\n".join(netlist_lines) + "\n"

    def compile_body(self) -> CompiledNetlistBody:
        netlist_lines = self._compile_body_lines()
        if self.expanded_graph is None:
            raise RuntimeError("Compiler did not produce an expanded graph.")
        return CompiledNetlistBody(
            lines=tuple(netlist_lines),
            node_map_forward=self.node_map_forward.copy(),
            node_map_inverse=self.node_map_inverse.copy(),
            expanded_graph=self.expanded_graph,
        )

    def _compile_body_lines(self) -> list[str]:
        self.node_map_forward = {}
        self.node_map_inverse = {}
        self.expanded_graph = self.graph.__class__()
        self.expanded_graph.graph.update(self.graph.graph)
        self.expanded_graph.add_nodes_from(
            (node_id, data.copy()) for node_id, data in self.graph.nodes(data=True)
        )

        self._build_node_maps()

        netlist_lines = ["* Generated Circuit"]
        netlist_lines.extend(self.global_directives)
        netlist_lines.append(".OPTIONS DEVICE GMIN=1e-8")
        netlist_lines.extend(self._compile_element_lines())
        netlist_lines.extend(self._compile_device_lines())
        return netlist_lines

    def _compile_element_lines(self) -> list[str]:
        spice_lines: list[str] = []
        for source_node, target_node, edge_key, edge_data in self.graph.edges(keys=True, data=True):
            if edge_data.get("is_device_link") is True:
                self.expanded_graph.add_edge(source_node, target_node, key=edge_key, **edge_data.copy())
                continue

            source_spice_node = self.node_map_forward[source_node]
            target_spice_node = self.node_map_forward[target_node]
            elements = edge_data["elements"]

            if len(elements) == 1:
                spice_lines.append(elements[0].to_spice(source_spice_node, target_spice_node))
                self.expanded_graph.add_edge(source_node, target_node, key=edge_key, **edge_data.copy())
                continue

            expanded_branch_nodes = [source_node]

            for step_index in range(1, len(elements)):
                hidden_node = f"_INT_{source_spice_node}_{target_spice_node}_{edge_key}_step{step_index}"
                expanded_branch_nodes.append(hidden_node)
                self.expanded_graph.add_node(hidden_node, is_hidden=True)

            expanded_branch_nodes.append(target_node)

            for index, element in enumerate(elements):
                start_node = expanded_branch_nodes[index]
                end_node = expanded_branch_nodes[index + 1]
                spice_start = (
                    start_node
                    if isinstance(start_node, str) and start_node.startswith("_INT_")
                    else self.node_map_forward[start_node]
                )
                spice_end = (
                    end_node
                    if isinstance(end_node, str) and end_node.startswith("_INT_")
                    else self.node_map_forward[end_node]
                )
                spice_lines.append(element.to_spice(spice_start, spice_end))
                self.expanded_graph.add_edge(start_node, end_node, elements=[element])

        return spice_lines

    def _compile_device_lines(self) -> list[str]:
        spice_lines: list[str] = []
        for _, data in self.graph.nodes(data=True):
            if data.get("is_device") is not True:
                continue

            device = data["device_obj"]
            terminal_nodes = data["ordered_nodes"]
            # Terminal node ids are user graph nodes, so this mapping preserves
            # the ground remap to SPICE node "0" for device terminals automatically.
            spice_terminal_nodes = [self.node_map_forward[node_id] for node_id in terminal_nodes]
            spice_lines.append(device.to_spice(spice_terminal_nodes))

        return spice_lines

    def _build_node_maps(self):
        next_node_index = 1
        for node_id, data in self.graph.nodes(data=True):
            if data.get("is_device") is True:
                continue
            if data.get("is_ground") is True:
                spice_id = "0"
            else:
                spice_id = f"N_{next_node_index}"
                next_node_index += 1
            self.node_map_forward[node_id] = spice_id
            self.node_map_inverse[spice_id] = node_id
