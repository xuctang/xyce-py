from __future__ import annotations

from collections.abc import Hashable
from pathlib import Path
import time
import warnings

import networkx as nx

from ._validation import validate_non_empty_string as _validate_non_empty_string
from .compiler import NetlistCompiler
from .engine import _execute_xyce_netlist, find_xyce_executable
from .models import CircuitElement, NTerminalDevice, SolveResult


def _validate_user_node_id(node_id: Hashable) -> Hashable:
    if isinstance(node_id, str) and node_id.startswith(("_DEV_", "_INT_")):
        raise ValueError("node_id cannot start with reserved prefixes '_DEV_' or '_INT_'.")
    return node_id


class CircuitTopologyError(RuntimeError):
    pass


class CircuitGraph:
    def __init__(
        self,
        xyce_path: str | None = None,
        base_out_dir: str = "_xyce_runs",
        solver_params: dict | None = None,
    ):
        self.G = nx.MultiDiGraph()
        self.global_directives: list[str] = []
        self.xyce_path = xyce_path or find_xyce_executable()
        self.base_out_dir = Path(base_out_dir).resolve()
        self.solver_params = dict(solver_params or {})

    def add_node(self, node_id: Hashable, is_ground: bool = False):
        if not isinstance(node_id, Hashable):
            raise TypeError("node_id must be hashable.")
        node_id = _validate_user_node_id(node_id)

        if node_id not in self.G:
            self.G.add_node(node_id)

        if not is_ground:
            return

        existing_ground = self._find_ground_node()
        if existing_ground is not None and existing_ground != node_id:
            raise ValueError("Only one ground node may be defined in the graph.")

        self.G.nodes[node_id]["is_ground"] = True

    def add_branch(self, node_a: Hashable, node_b: Hashable, elements: list[CircuitElement]):
        if node_a not in self.G:
            self.add_node(node_a)
        if node_b not in self.G:
            self.add_node(node_b)
        if not isinstance(elements, list):
            raise TypeError("elements must be provided as a list of CircuitElement instances.")
        if not elements:
            raise ValueError("elements must be a non-empty list of CircuitElement instances.")
        if not all(isinstance(element, CircuitElement) for element in elements):
            raise TypeError("elements must contain only CircuitElement instances.")

        self.G.add_edge(node_a, node_b, elements=elements)

    def add_device(self, device: NTerminalDevice, nodes: list[Hashable]):
        if not isinstance(device, NTerminalDevice):
            raise TypeError("device must be an NTerminalDevice instance.")
        if not isinstance(nodes, list):
            raise TypeError("nodes must be provided as a list of node identifiers.")
        if len(nodes) != device.expected_terminals:
            raise ValueError(
                f"nodes must contain exactly {device.expected_terminals} node identifiers."
            )

        device_node_id = f"_DEV_{device.name}"
        if device_node_id in self.G:
            raise ValueError(f"Device node '{device_node_id}' already exists in the graph.")

        for node in nodes:
            if node not in self.G:
                self.add_node(node)

        self.G.add_node(
            device_node_id,
            is_device=True,
            device_obj=device,
            ordered_nodes=list(nodes),
        )
        for node in nodes:
            self.G.add_edge(device_node_id, node, is_device_link=True)

    def add_model(self, model_string: str):
        directive = _validate_non_empty_string(model_string, "model_string")
        if not directive.startswith(".MODEL"):
            raise ValueError("model_string must start with '.MODEL'.")
        self.global_directives.append(directive)

    def add_options(self, options_string: str):
        directive = _validate_non_empty_string(options_string, "options_string")
        if not directive.startswith(".OPTIONS"):
            raise ValueError("options_string must start with '.OPTIONS'.")
        self.global_directives.append(directive)

    def add_subcircuit(self, subckt_string: str):
        directive = _validate_non_empty_string(subckt_string, "subckt_string").strip()
        if not directive.startswith(".SUBCKT"):
            raise ValueError("subckt_string must start with '.SUBCKT'.")
        if not directive.endswith(".ENDS"):
            raise ValueError("subckt_string must end with '.ENDS'.")
        # Raw SPICE subcircuits are treated as opaque text here. Arity mismatches
        # between a .SUBCKT definition and a Subcircuit instance are left for Xyce
        # to diagnose at execution time instead of being parsed heuristically.
        self.global_directives.append(directive)

    def simulate(
        self,
        analysis_cmd: str,
        *args,
        print_vars: list[str] | None = None,
        inplace: bool = False,
    ) -> SolveResult:
        analysis_type, resolved_analysis_cmd, resolved_print_vars = self._normalize_simulation_request(
            analysis_cmd,
            args,
            print_vars,
        )

        self._validate_topology()
        compiler = NetlistCompiler(self.G, self.global_directives)
        compiled_body = compiler.compile_body()
        if compiled_body.expanded_graph is None:
            raise RuntimeError("Compiler did not produce an expanded graph.")
        netlist_lines = list(compiled_body.lines)
        resolved_print_vars = self._resolve_print_vars(
            resolved_print_vars,
            compiled_body.node_map_forward,
        )
        print_analysis_type = "DC" if analysis_type == "OP" else analysis_type
        netlist_lines.append(resolved_analysis_cmd)
        netlist_lines.append(
            f".PRINT {print_analysis_type} FORMAT=CSV FILE=output.csv {' '.join(resolved_print_vars)}"
        )
        netlist_lines.append(".END")
        final_netlist = "\n".join(netlist_lines) + "\n"

        execution_result = _execute_xyce_netlist(
            xyce_path=self.xyce_path,
            base_out_dir=self.base_out_dir,
            netlist_content=final_netlist,
            csv_name="output.csv",
            run_name=f"simulate_{analysis_type.lower()}_{time.time_ns()}",
            keep_run_dir=False,
        )

        original_graph = self.G.copy()
        expanded_graph = compiled_body.expanded_graph
        waveforms = execution_result.waveforms
        if inplace:
            if len(waveforms) != 1:
                raise ValueError(
                    "Cannot use inplace=True with multi-point sweeps. "
                    "Extract data from SolveResult.waveforms instead."
                )
            self._apply_inplace_solution(waveforms, compiled_body.node_map_inverse)

        return SolveResult(
            original_graph=original_graph,
            expanded_graph=expanded_graph,
            netlist=final_netlist,
            waveforms=waveforms,
            solve_time_sec=execution_result.solve_time_sec,
            stdout=execution_result.stdout,
            node_map_inverse=compiled_body.node_map_inverse.copy(),
        )

    def simulate_op(
        self,
        print_vars: list[str] | None = None,
        inplace: bool = False,
    ) -> SolveResult:
        return self.simulate(".OP", print_vars=print_vars, inplace=inplace)

    def simulate_transient(
        self,
        step: str,
        stop: str,
        start: str = "0",
        print_vars: list[str] | None = None,
        inplace: bool = False,
    ) -> SolveResult:
        step = _validate_non_empty_string(step, "step")
        stop = _validate_non_empty_string(stop, "stop")
        start = _validate_non_empty_string(start, "start")
        analysis_cmd = f".TRAN {step} {stop}"
        if start != "0":
            analysis_cmd += f" {start}"
        return self.simulate(analysis_cmd, print_vars=print_vars, inplace=inplace)

    def simulate_ac(
        self,
        sweep_type: str,
        points: str,
        start_freq: str,
        stop_freq: str,
        print_vars: list[str] | None = None,
    ) -> SolveResult:
        sweep_type = _validate_non_empty_string(sweep_type, "sweep_type")
        points = _validate_non_empty_string(points, "points")
        start_freq = _validate_non_empty_string(start_freq, "start_freq")
        stop_freq = _validate_non_empty_string(stop_freq, "stop_freq")
        return self.simulate(
            f".AC {sweep_type} {points} {start_freq} {stop_freq}",
            print_vars=print_vars,
            inplace=False,
        )

    def simulate_dc(
        self,
        source_name: str,
        start: str,
        stop: str,
        step: str,
        print_vars: list[str] | None = None,
    ) -> SolveResult:
        source_name = _validate_non_empty_string(source_name, "source_name")
        start = _validate_non_empty_string(start, "start")
        stop = _validate_non_empty_string(stop, "stop")
        step = _validate_non_empty_string(step, "step")
        return self.simulate(
            f".DC {source_name} {start} {stop} {step}",
            print_vars=print_vars,
            inplace=False,
        )

    def _validate_topology(self):
        ground_node_ids = [
            node_id for node_id, data in self.G.nodes(data=True) if data.get("is_ground") is True
        ]
        if not ground_node_ids:
            raise CircuitTopologyError("Circuit has no ground reference.")
        if len(ground_node_ids) > 1:
            raise CircuitTopologyError("Circuit has multiple ground references.")

        ground_node_id = ground_node_ids[0]
        for component_nodes in nx.weakly_connected_components(self.G):
            if ground_node_id not in component_nodes:
                raise CircuitTopologyError("Floating subgraph detected with no path to ground.")

    def _find_ground_node(self):
        for node_id, data in self.G.nodes(data=True):
            if data.get("is_ground"):
                return node_id
        return None

    def _resolve_print_vars(
        self,
        print_vars: list[str] | None,
        user_to_spice_node: dict[object, str],
    ) -> list[str]:
        if print_vars is None:
            default_print_vars = [
                f"V({spice_node})" for spice_node in user_to_spice_node.values() if spice_node != "0"
            ]
            if not default_print_vars:
                raise ValueError("No non-ground user nodes available for default print_vars.")
            return default_print_vars

        if not isinstance(print_vars, list) or not print_vars:
            raise ValueError("print_vars must be a non-empty list of strings.")
        return [_validate_non_empty_string(print_var, "print_vars item") for print_var in print_vars]

    def _normalize_simulation_request(
        self,
        analysis_cmd: str,
        legacy_args: tuple[object, ...],
        print_vars: list[str] | None,
    ) -> tuple[str, str, list[str] | None]:
        if legacy_args:
            if len(legacy_args) > 2:
                raise TypeError("simulate() accepts at most two deprecated positional arguments.")
            legacy_analysis_type = _validate_non_empty_string(analysis_cmd, "analysis_type").upper()
            resolved_analysis_cmd = _validate_non_empty_string(legacy_args[0], "analysis_cmd").strip()
            if not resolved_analysis_cmd.upper().startswith(f".{legacy_analysis_type}"):
                raise ValueError(f"analysis_cmd must start with '.{legacy_analysis_type}'.")
            if len(legacy_args) == 2:
                if print_vars is not None:
                    raise TypeError("print_vars must be passed once.")
                print_vars = legacy_args[1]
            warnings.warn(
                "simulate(analysis_type, analysis_cmd, ...) is deprecated; "
                "use simulate(analysis_cmd, ...) instead.",
                DeprecationWarning,
                stacklevel=3,
            )
            return legacy_analysis_type, resolved_analysis_cmd, print_vars

        resolved_analysis_cmd = _validate_non_empty_string(analysis_cmd, "analysis_cmd").strip()
        analysis_type = self._infer_analysis_type(resolved_analysis_cmd)
        return analysis_type, resolved_analysis_cmd, print_vars

    def _infer_analysis_type(self, analysis_cmd: str) -> str:
        directive_token = analysis_cmd.split(maxsplit=1)[0].upper()
        if not directive_token.startswith("."):
            raise ValueError("analysis_cmd must start with a SPICE analysis directive like '.OP'.")
        analysis_type = directive_token[1:]
        if analysis_type not in {"OP", "TRAN", "AC", "DC"}:
            raise ValueError("analysis_cmd must start with one of: .OP, .TRAN, .AC, .DC.")
        return analysis_type

    def _apply_inplace_solution(self, waveforms, spice_to_user_node: dict[str, object]):
        node_voltage_updates: dict[object, object] = {}
        solution_row = waveforms.iloc[0]
        for column, value in solution_row.items():
            if not (isinstance(column, str) and column.startswith("V(") and column.endswith(")")):
                continue
            spice_id = column[2:-1]
            if spice_id == "0" or spice_id not in spice_to_user_node:
                continue
            user_node_id = spice_to_user_node[spice_id]
            if "solved_voltage" in self.G.nodes[user_node_id]:
                raise RuntimeError(
                    "Attribute 'solved_voltage' already exists on node. Use inplace=False."
                )
            node_voltage_updates[user_node_id] = value

        for user_node_id, value in node_voltage_updates.items():
            self.G.nodes[user_node_id]["solved_voltage"] = value
