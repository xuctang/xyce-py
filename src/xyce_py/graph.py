from __future__ import annotations

from collections.abc import Hashable
from pathlib import Path
import time
import warnings

import networkx as nx

from .compiler import NetlistCompiler
from .engine import _execute_xyce_netlist, find_xyce_executable
from .models import CircuitElement, NTerminalDevice, SolveResult


def _validate_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


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
        directive = _validate_non_empty_string(subckt_string, "subckt_string")
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

        original_graph = self.G.copy()
        self._validate_topology()
        compiler = NetlistCompiler(self.G, self.global_directives)
        netlist_lines = compiler._compile_body_lines()
        resolved_print_vars = self._resolve_print_vars(
            resolved_print_vars,
            compiler.node_map_forward,
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

        expanded_graph = compiler.expanded_graph.copy()
        waveforms = execution_result.waveforms
        if inplace:
            if len(waveforms) != 1:
                raise ValueError(
                    "Cannot use inplace=True with multi-point sweeps. "
                    "Extract data from SolveResult.waveforms instead."
                )
            self._apply_inplace_solution(waveforms, compiler.node_map_inverse)

        return SolveResult(
            original_graph=original_graph,
            expanded_graph=expanded_graph,
            netlist=final_netlist,
            waveforms=waveforms,
            solve_time_sec=execution_result.solve_time_sec,
            stdout=execution_result.stdout,
            node_map_inverse=compiler.node_map_inverse.copy(),
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
        ground_nodes = [
            node_id for node_id, data in self.G.nodes(data=True) if data.get("is_ground") is True
        ]
        if not ground_nodes:
            raise CircuitTopologyError("Circuit has no ground reference.")
        if len(ground_nodes) > 1:
            raise CircuitTopologyError("Circuit has multiple ground references.")

        ground_node = ground_nodes[0]
        components = list(nx.weakly_connected_components(self.G))
        if len(components) > 1:
            for component in components:
                if ground_node not in component:
                    raise CircuitTopologyError("Floating subgraph detected with no path to ground.")

    def _find_ground_node(self):
        for node_id, data in self.G.nodes(data=True):
            if data.get("is_ground"):
                return node_id
        return None

    def _resolve_print_vars(
        self,
        print_vars: list[str] | None,
        node_map_forward: dict[object, str],
    ) -> list[str]:
        if print_vars is None:
            resolved = [f"V({spice_id})" for spice_id in node_map_forward.values() if spice_id != "0"]
            if not resolved:
                raise ValueError("No non-ground user nodes available for default print_vars.")
            return resolved

        if not isinstance(print_vars, list) or not print_vars:
            raise ValueError("print_vars must be a non-empty list of strings.")
        return [_validate_non_empty_string(print_var, "print_vars item") for print_var in print_vars]

    def _normalize_simulation_request(
        self,
        analysis_cmd: str,
        args: tuple[object, ...],
        print_vars: list[str] | None,
    ) -> tuple[str, str, list[str] | None]:
        if args:
            if len(args) > 2:
                raise TypeError("simulate() accepts at most two deprecated positional arguments.")
            legacy_analysis_type = _validate_non_empty_string(analysis_cmd, "analysis_type").upper()
            resolved_analysis_cmd = _validate_non_empty_string(args[0], "analysis_cmd").strip()
            if not resolved_analysis_cmd.upper().startswith(f".{legacy_analysis_type}"):
                raise ValueError(f"analysis_cmd must start with '.{legacy_analysis_type}'.")
            if len(args) == 2:
                if print_vars is not None:
                    raise TypeError("print_vars must be passed once.")
                print_vars = args[1]
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
        first_token = analysis_cmd.split(maxsplit=1)[0].upper()
        if not first_token.startswith("."):
            raise ValueError("analysis_cmd must start with a SPICE analysis directive like '.OP'.")
        analysis_type = first_token[1:]
        if analysis_type not in {"OP", "TRAN", "AC", "DC"}:
            raise ValueError("analysis_cmd must start with one of: .OP, .TRAN, .AC, .DC.")
        return analysis_type

    def _apply_inplace_solution(self, waveforms, node_map_inverse: dict[str, object]):
        solved_values: dict[object, object] = {}
        row = waveforms.iloc[0]
        for column, value in row.items():
            if not (isinstance(column, str) and column.startswith("V(") and column.endswith(")")):
                continue
            spice_id = column[2:-1]
            if spice_id == "0" or spice_id not in node_map_inverse:
                continue
            original_id = node_map_inverse[spice_id]
            if "solved_voltage" in self.G.nodes[original_id]:
                raise RuntimeError(
                    "Attribute 'solved_voltage' already exists on node. Use inplace=False."
                )
            solved_values[original_id] = value

        for original_id, value in solved_values.items():
            self.G.nodes[original_id]["solved_voltage"] = value
