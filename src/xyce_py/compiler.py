from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import networkx as nx


@dataclass(frozen=True)
class NetlistBody:
    lines: tuple[str, ...]
    user_to_spice_node: Mapping[object, str]
    spice_to_user_node: Mapping[str, object]
    expanded_graph: nx.MultiDiGraph


class NetlistCompiler:
    def __init__(self, graph: nx.MultiDiGraph, spice_directives: list[str]):
        self._graph = graph
        self._spice_directives = tuple(spice_directives)
        self._user_to_spice_node: dict[object, str] = {}
        self._spice_to_user_node: dict[str, object] = {}
        self._expanded_graph: nx.MultiDiGraph | None = None

    @property
    def user_to_spice_node(self) -> Mapping[object, str]:
        return MappingProxyType(self._user_to_spice_node.copy())

    @property
    def spice_to_user_node(self) -> Mapping[str, object]:
        return MappingProxyType(self._spice_to_user_node.copy())

    @property
    def expanded_graph(self) -> nx.MultiDiGraph | None:
        if self._expanded_graph is None:
            return None
        return self._expanded_graph.copy()

    def compile(self) -> str:
        netlist_lines = list(self.compile_body().lines)
        netlist_lines.append(".END")
        return "\n".join(netlist_lines) + "\n"

    def compile_body(self) -> NetlistBody:
        netlist_lines = self._build_body_lines()
        if self._expanded_graph is None:
            raise RuntimeError("Compiler did not produce an expanded graph.")
        return NetlistBody(
            lines=tuple(netlist_lines),
            user_to_spice_node=MappingProxyType(self._user_to_spice_node.copy()),
            spice_to_user_node=MappingProxyType(self._spice_to_user_node.copy()),
            expanded_graph=self._expanded_graph.copy(),
        )

    def _build_body_lines(self) -> list[str]:
        self._user_to_spice_node = {}
        self._spice_to_user_node = {}
        self._expanded_graph = self._graph.__class__()
        self._expanded_graph.graph.update(self._graph.graph)
        self._expanded_graph.add_nodes_from(
            (node_id, data.copy()) for node_id, data in self._graph.nodes(data=True)
        )

        self._build_user_spice_node_mappings()

        netlist_lines = ["* Generated Circuit"]
        netlist_lines.extend(self._spice_directives)
        netlist_lines.append(".OPTIONS DEVICE GMIN=1e-8")
        netlist_lines.extend(self._compile_element_lines())
        netlist_lines.extend(self._compile_device_lines())
        return netlist_lines

    def _compile_element_lines(self) -> list[str]:
        spice_lines: list[str] = []
        for source_node, target_node, edge_key, edge_data in self._graph.edges(keys=True, data=True):
            if edge_data.get("is_device_link") is True:
                self._expanded_graph.add_edge(source_node, target_node, key=edge_key, **edge_data.copy())
                continue

            source_spice_node = self._user_to_spice_node[source_node]
            target_spice_node = self._user_to_spice_node[target_node]
            elements = edge_data["elements"]

            if len(elements) == 1:
                spice_lines.append(elements[0].to_spice(source_spice_node, target_spice_node))
                self._expanded_graph.add_edge(source_node, target_node, key=edge_key, **edge_data.copy())
                continue

            expanded_branch_nodes = [source_node]

            for step_index in range(1, len(elements)):
                hidden_node = f"_INT_{source_spice_node}_{target_spice_node}_{edge_key}_step{step_index}"
                expanded_branch_nodes.append(hidden_node)
                self._expanded_graph.add_node(hidden_node, is_hidden=True)

            expanded_branch_nodes.append(target_node)

            for index, element in enumerate(elements):
                start_node = expanded_branch_nodes[index]
                end_node = expanded_branch_nodes[index + 1]
                spice_start = (
                    start_node
                    if isinstance(start_node, str) and start_node.startswith("_INT_")
                    else self._user_to_spice_node[start_node]
                )
                spice_end = (
                    end_node
                    if isinstance(end_node, str) and end_node.startswith("_INT_")
                    else self._user_to_spice_node[end_node]
                )
                spice_lines.append(element.to_spice(spice_start, spice_end))
                self._expanded_graph.add_edge(start_node, end_node, elements=[element])

        return spice_lines

    def _compile_device_lines(self) -> list[str]:
        spice_lines: list[str] = []
        for _, data in self._graph.nodes(data=True):
            if data.get("is_device") is not True:
                continue

            device = data["device_obj"]
            terminal_nodes = data["ordered_nodes"]
            # Terminal node ids are user graph nodes, so this mapping preserves
            # the ground remap to SPICE node "0" for device terminals automatically.
            spice_terminal_nodes = [self._user_to_spice_node[node_id] for node_id in terminal_nodes]
            spice_lines.append(device.to_spice(spice_terminal_nodes))

        return spice_lines

    def _build_user_spice_node_mappings(self):
        next_node_index = 1
        for node_id, data in self._graph.nodes(data=True):
            if data.get("is_device") is True:
                continue
            if data.get("is_ground") is True:
                spice_id = "0"
            else:
                spice_id = f"N_{next_node_index}"
                next_node_index += 1
            self._user_to_spice_node[node_id] = spice_id
            self._spice_to_user_node[spice_id] = node_id
