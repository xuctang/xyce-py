from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections.abc import Hashable
from typing import Optional, Union

import networkx as nx
import pandas as pd


ValueLike = Union[str, float]


def _validate_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value


def _validate_numeric(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    return float(value)


def _validate_value_like(value: object, field_name: str) -> ValueLike:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a non-empty string or numeric value.")
    return float(value)


def _format_value(value: ValueLike) -> str:
    return value if isinstance(value, str) else str(value)


def _validate_spice_nodes(node_pos: object, node_neg: object) -> tuple[str, str]:
    return (
        _validate_non_empty_string(node_pos, "node_pos"),
        _validate_non_empty_string(node_neg, "node_neg"),
    )


def _validate_mapped_nodes(mapped_nodes: object, expected_terminals: int) -> list[str]:
    if not isinstance(mapped_nodes, list):
        raise TypeError("mapped_nodes must be provided as a list of node names.")
    if len(mapped_nodes) != expected_terminals:
        raise ValueError(f"mapped_nodes must contain exactly {expected_terminals} node names.")
    return [
        _validate_non_empty_string(node_name, f"mapped_nodes[{index}]")
        for index, node_name in enumerate(mapped_nodes)
    ]


@dataclass
class CircuitElement(ABC):
    name: str

    def __post_init__(self):
        self.name = _validate_non_empty_string(self.name, "name")

    @abstractmethod
    def to_spice(self, node_pos: str, node_neg: str) -> str:
        raise NotImplementedError


@dataclass
class NTerminalDevice(ABC):
    name: str
    model_name: str

    def __post_init__(self):
        self.name = _validate_non_empty_string(self.name, "name")
        self.model_name = _validate_non_empty_string(self.model_name, "model_name")

    @property
    @abstractmethod
    def expected_terminals(self) -> int:
        raise NotImplementedError

    def _validated_mapped_nodes(self, mapped_nodes: object) -> list[str]:
        # Keep this validation at the model boundary even though CircuitGraph
        # already checks arity when devices are added to the topology.
        return _validate_mapped_nodes(mapped_nodes, self.expected_terminals)

    @abstractmethod
    def to_spice(self, mapped_nodes: list[str]) -> str:
        raise NotImplementedError


@dataclass
class Resistor(CircuitElement):
    value: ValueLike

    def __post_init__(self):
        super().__post_init__()
        self.value = _validate_value_like(self.value, "value")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        return f"R_{self.name} {node_pos} {node_neg} {_format_value(self.value)}"


@dataclass
class Capacitor(CircuitElement):
    value: ValueLike

    def __post_init__(self):
        super().__post_init__()
        self.value = _validate_value_like(self.value, "value")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        return f"C_{self.name} {node_pos} {node_neg} {_format_value(self.value)}"


@dataclass
class Inductor(CircuitElement):
    value: ValueLike

    def __post_init__(self):
        super().__post_init__()
        self.value = _validate_value_like(self.value, "value")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        return f"L_{self.name} {node_pos} {node_neg} {_format_value(self.value)}"


@dataclass
class VoltageSource(CircuitElement):
    dc_value: float
    transient_expr: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.dc_value = _validate_numeric(self.dc_value, "dc_value")
        if self.transient_expr is not None:
            self.transient_expr = _validate_non_empty_string(self.transient_expr, "transient_expr")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        spice_line = f"V_{self.name} {node_pos} {node_neg} DC {self.dc_value}"
        if self.transient_expr is not None:
            spice_line += f" {self.transient_expr}"
        return spice_line


@dataclass
class CurrentSource(CircuitElement):
    dc_value: float
    transient_expr: Optional[str] = None

    def __post_init__(self):
        super().__post_init__()
        self.dc_value = _validate_numeric(self.dc_value, "dc_value")
        if self.transient_expr is not None:
            self.transient_expr = _validate_non_empty_string(self.transient_expr, "transient_expr")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        spice_line = f"I_{self.name} {node_pos} {node_neg} DC {self.dc_value}"
        if self.transient_expr is not None:
            spice_line += f" {self.transient_expr}"
        return spice_line


@dataclass
class Diode(CircuitElement):
    model_name: str

    def __post_init__(self):
        super().__post_init__()
        self.model_name = _validate_non_empty_string(self.model_name, "model_name")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        return f"D_{self.name} {node_pos} {node_neg} {self.model_name}"


@dataclass
class BJT(NTerminalDevice):
    @property
    def expected_terminals(self) -> int:
        return 3

    def to_spice(self, mapped_nodes: list[str]) -> str:
        collector, base, emitter = self._validated_mapped_nodes(mapped_nodes)
        return f"Q_{self.name} {collector} {base} {emitter} {self.model_name}"


@dataclass
class MOSFET(NTerminalDevice):
    @property
    def expected_terminals(self) -> int:
        return 4

    def to_spice(self, mapped_nodes: list[str]) -> str:
        drain, gate, source, bulk = self._validated_mapped_nodes(mapped_nodes)
        return f"M_{self.name} {drain} {gate} {source} {bulk} {self.model_name}"


@dataclass
class Subcircuit(NTerminalDevice):
    terminals: int

    def __post_init__(self):
        super().__post_init__()
        if isinstance(self.terminals, bool) or not isinstance(self.terminals, int):
            raise TypeError("terminals must be an integer.")
        if self.terminals <= 0:
            raise ValueError("terminals must be a positive integer.")

    @property
    def expected_terminals(self) -> int:
        return self.terminals

    def to_spice(self, mapped_nodes: list[str]) -> str:
        mapped_nodes = self._validated_mapped_nodes(mapped_nodes)
        return f"X_{self.name} {' '.join(mapped_nodes)} {self.model_name}"


@dataclass
class BehavioralSource(CircuitElement):
    equation: str
    source_type: str

    def __post_init__(self):
        super().__post_init__()
        self.equation = _validate_non_empty_string(self.equation, "equation")
        self.source_type = _validate_non_empty_string(self.source_type, "source_type")
        if self.source_type not in {"V", "I"}:
            raise ValueError("source_type must be exactly 'V' or 'I'.")

    def to_spice(self, node_pos: str, node_neg: str) -> str:
        node_pos, node_neg = _validate_spice_nodes(node_pos, node_neg)
        return f"B_{self.name} {node_pos} {node_neg} {self.source_type}={{{self.equation}}}"


@dataclass
class SolveResult:
    original_graph: nx.MultiDiGraph
    expanded_graph: nx.MultiDiGraph
    netlist: str
    waveforms: pd.DataFrame
    solve_time_sec: float
    stdout: str
    node_map_inverse: dict[str, Hashable]

    def translated_waveforms(self) -> pd.DataFrame:
        translated = self.waveforms.copy()
        renamed_columns: dict[str, str] = {}

        for column in translated.columns:
            if not (isinstance(column, str) and column.startswith("V(") and column.endswith(")")):
                continue
            spice_id = column[2:-1]
            if spice_id not in self.node_map_inverse:
                continue
            renamed_columns[column] = f"V({self.node_map_inverse[spice_id]})"

        return translated.rename(columns=renamed_columns)
