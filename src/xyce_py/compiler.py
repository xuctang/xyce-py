from __future__ import annotations

import networkx as nx


class NetlistCompiler:
    def __init__(self, graph: nx.MultiDiGraph, global_directives: list[str]):
        self.graph = graph
        self.global_directives = global_directives
        self.node_map_forward: dict[object, str] = {}
        self.node_map_inverse: dict[str, object] = {}
        self.expanded_graph: nx.MultiDiGraph | None = None

    def compile(self) -> str:
        netlist_lines = self._compile_body_lines()
        netlist_lines.append(".END")
        return "\n".join(netlist_lines) + "\n"

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
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if data.get("is_device_link") is True:
                self.expanded_graph.add_edge(u, v, key=key, **data.copy())
                continue

            spice_u = self.node_map_forward[u]
            spice_v = self.node_map_forward[v]
            elements = data["elements"]

            if len(elements) == 1:
                spice_lines.append(elements[0].to_spice(spice_u, spice_v))
                self.expanded_graph.add_edge(u, v, key=key, **data.copy())
                continue

            branch_nodes = [u]

            for step_index in range(1, len(elements)):
                hidden_node = f"_INT_{spice_u}_{spice_v}_{key}_step{step_index}"
                branch_nodes.append(hidden_node)
                self.expanded_graph.add_node(hidden_node, is_hidden=True)

            branch_nodes.append(v)

            for index, element in enumerate(elements):
                start_node = branch_nodes[index]
                end_node = branch_nodes[index + 1]
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

            device_obj = data["device_obj"]
            ordered_nodes = data["ordered_nodes"]
            # ordered_nodes are user graph node ids, so this mapping preserves the
            # ground remap to SPICE node "0" for device terminals automatically.
            mapped_nodes = [self.node_map_forward[node_id] for node_id in ordered_nodes]
            spice_lines.append(device_obj.to_spice(mapped_nodes))

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
