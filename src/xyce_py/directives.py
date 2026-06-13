from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re
from typing import Union

from ._validation import validate_non_empty_string as _validate_non_empty_string
from .outputs import validate_relative_output_path


DirectiveValue = Union[str, int, float]

_SPICE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_spice_identifier(value: object, field_name: str) -> str:
    value = _validate_non_empty_string(value, field_name)
    if not _SPICE_IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a SPICE identifier.")
    return value


def _format_directive_value(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return _validate_non_empty_string(value, field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a non-empty string or numeric value.")
    return str(float(value))


def _normalize_directive_items(items: Iterable[str], field_name: str) -> tuple[str, ...]:
    if not isinstance(items, list):
        raise TypeError(f"{field_name} must be provided as a list of strings.")
    if not items:
        raise ValueError(f"{field_name} must be a non-empty list of strings.")
    return tuple(_validate_non_empty_string(item, f"{field_name} item") for item in items)


def _normalize_analysis_type(analysis_type: object) -> str:
    analysis_type = _validate_non_empty_string(analysis_type, "analysis_type").upper()
    if analysis_type.startswith("."):
        raise ValueError("analysis_type must not include the leading '.'.")
    return analysis_type


@dataclass(frozen=True)
class RawDirective:
    text: str

    def __post_init__(self):
        text = _validate_non_empty_string(self.text, "text").strip()
        if not text.startswith("."):
            raise ValueError("text must start with '.'.")
        object.__setattr__(self, "text", text)

    def to_spice(self) -> str:
        return self.text


@dataclass(frozen=True)
class ParameterDirective:
    name: str
    value: DirectiveValue

    def __post_init__(self):
        object.__setattr__(self, "name", _validate_spice_identifier(self.name, "name"))
        object.__setattr__(self, "value", _format_directive_value(self.value, "value"))

    def to_spice(self) -> str:
        return f".PARAM {self.name}={self.value}"


@dataclass(frozen=True)
class PrintDirective:
    analysis_type: str
    variables: tuple[str, ...]
    file: str = "output.csv"
    output_format: str = "CSV"

    def __init__(
        self,
        analysis_type: str,
        variables: list[str],
        *,
        file: str = "output.csv",
        output_format: str = "CSV",
    ):
        object.__setattr__(self, "analysis_type", analysis_type)
        object.__setattr__(self, "variables", variables)
        object.__setattr__(self, "file", file)
        object.__setattr__(self, "output_format", output_format)
        self.__post_init__()

    def __post_init__(self):
        object.__setattr__(self, "analysis_type", _normalize_analysis_type(self.analysis_type))
        object.__setattr__(self, "variables", _normalize_directive_items(self.variables, "variables"))
        object.__setattr__(self, "file", validate_relative_output_path(self.file, "file"))
        output_format = _validate_non_empty_string(self.output_format, "output_format").upper()
        if output_format != "CSV":
            raise ValueError("output_format must be exactly 'CSV'.")
        object.__setattr__(self, "output_format", output_format)

    def to_spice(self) -> str:
        return (
            f".PRINT {self.analysis_type} FORMAT={self.output_format} "
            f"FILE={self.file} {' '.join(self.variables)}"
        )


@dataclass(frozen=True)
class MeasureDirective:
    analysis_type: str
    name: str
    expression: str

    def __post_init__(self):
        object.__setattr__(self, "analysis_type", _normalize_analysis_type(self.analysis_type))
        object.__setattr__(self, "name", _validate_spice_identifier(self.name, "name"))
        object.__setattr__(self, "expression", _validate_non_empty_string(self.expression, "expression"))

    def to_spice(self) -> str:
        return f".MEASURE {self.analysis_type} {self.name} {self.expression}"
