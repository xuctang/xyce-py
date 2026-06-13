from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import time
from types import MappingProxyType
from typing import Literal, Union

from ._validation import validate_non_empty_string as _validate_non_empty_string
from .outputs import (
    OutputArtifact,
    OutputKind,
    OutputSpec,
    collect_output_artifacts,
    normalize_output_specs,
    validate_relative_output_path,
)


ConfigValue = Union[str, int, float]
ReportKind = Literal["csv", "text"]


def _validate_token(value: object, field_name: str) -> str:
    token = _validate_non_empty_string(value, field_name).strip()
    if any(character.isspace() for character in token):
        raise ValueError(f"{field_name} must be a single netlist token.")
    return token


def _validate_directive_token(value: object, field_name: str) -> str:
    directive = _validate_token(value, field_name)
    if not directive.startswith("."):
        raise ValueError(f"{field_name} must start with '.'.")
    if directive.upper() == ".END":
        raise ValueError(f"{field_name} must not be '.END'.")
    return directive


def _validate_optional_expression(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _validate_non_empty_string(value, field_name).strip()


def _format_config_value(value: object, field_name: str) -> str:
    if isinstance(value, str):
        return _validate_non_empty_string(value, field_name).strip()
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a non-empty string or numeric value.")
    return str(float(value))


def _normalize_sequence(
    values: object,
    field_name: str,
    *,
    allow_empty: bool,
    token_items: bool = False,
) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{field_name} must be provided as a list or tuple of strings.")
    if not allow_empty and not values:
        raise ValueError(f"{field_name} must be a non-empty list or tuple of strings.")

    normalized_values: list[str] = []
    for value in values:
        if token_items:
            normalized_values.append(_validate_token(value, f"{field_name} item"))
        else:
            normalized_values.append(
                _validate_non_empty_string(value, f"{field_name} item").strip()
            )
    return tuple(normalized_values)


def _normalize_parameters(values: object, field_name: str) -> Mapping[str, str]:
    if values is None:
        return MappingProxyType({})
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping of parameter names to values.")

    normalized_values: dict[str, str] = {}
    for parameter_name, parameter_value in values.items():
        parameter_name = _validate_token(parameter_name, f"{field_name} key")
        if parameter_name in normalized_values:
            raise ValueError(f"Duplicate parameter name: {parameter_name!r}.")
        normalized_values[parameter_name] = _format_config_value(
            parameter_value,
            f"{field_name} value",
        )
    return MappingProxyType(normalized_values)


def _format_parameters(parameters: Mapping[str, str]) -> str:
    return " ".join(
        f"{parameter_name}={parameter_value}"
        for parameter_name, parameter_value in parameters.items()
    )


def _validate_analysis_type(value: object) -> str:
    analysis_type = _validate_token(value, "analysis_type").upper()
    if analysis_type.startswith("."):
        raise ValueError("analysis_type must not include the leading '.'.")
    return analysis_type


def _normalize_report_kind(value: object) -> ReportKind:
    kind = _validate_token(value, "kind").lower()
    if kind not in {"csv", "text"}:
        raise ValueError("kind must be exactly 'csv' or 'text'.")
    return kind


def _normalize_boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean.")
    return value


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping.")
    return value


def _reject_unknown_keys(
    mapping: Mapping[str, object],
    allowed_keys: set[str],
    class_name: str,
) -> None:
    unknown_keys = sorted(set(mapping) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"{class_name} received unknown keys: {unknown_keys!r}.")


def _normalize_spec_sequence(
    values: object,
    field_name: str,
    spec_type: type,
) -> tuple[object, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple.")

    normalized_values = []
    for value in values:
        if isinstance(value, spec_type):
            normalized_values.append(value)
        elif isinstance(value, Mapping):
            normalized_values.append(spec_type.from_mapping(value))
        else:
            raise TypeError(
                f"{field_name} items must be {spec_type.__name__} instances or mappings."
            )
    return tuple(normalized_values)


@dataclass(frozen=True)
class XyceDirectiveSpec:
    directive: str
    positional: tuple[str, ...] = field(default_factory=tuple)
    parameters: Mapping[str, ConfigValue] | None = None
    expression: str | None = None

    def __post_init__(self):
        object.__setattr__(
            self,
            "directive",
            _validate_directive_token(self.directive, "directive"),
        )
        object.__setattr__(
            self,
            "positional",
            _normalize_sequence(self.positional, "positional", allow_empty=True),
        )
        object.__setattr__(self, "parameters", _normalize_parameters(self.parameters, "parameters"))
        object.__setattr__(
            self,
            "expression",
            _validate_optional_expression(self.expression, "expression"),
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceDirectiveSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {"directive", "positional", "parameters", "expression"},
            cls.__name__,
        )
        if "directive" not in mapping:
            raise KeyError("directive")
        return cls(
            directive=mapping["directive"],
            positional=mapping.get("positional", ()),
            parameters=mapping.get("parameters"),
            expression=mapping.get("expression"),
        )

    def to_spice(self) -> str:
        parts = [self.directive, *self.positional]
        if self.parameters:
            parts.append(_format_parameters(self.parameters))
        if self.expression is not None:
            parts.append(self.expression)
        return " ".join(parts)


@dataclass(frozen=True)
class XyceAnalysisSpec(XyceDirectiveSpec):
    pass


@dataclass(frozen=True)
class XyceModelSpec:
    model_name: str
    model_type: str
    parameters: Mapping[str, ConfigValue] | None = None

    def __post_init__(self):
        object.__setattr__(self, "model_name", _validate_token(self.model_name, "model_name"))
        object.__setattr__(self, "model_type", _validate_token(self.model_type, "model_type"))
        object.__setattr__(self, "parameters", _normalize_parameters(self.parameters, "parameters"))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceModelSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(mapping, {"model_name", "model_type", "parameters"}, cls.__name__)
        for required_key in ("model_name", "model_type"):
            if required_key not in mapping:
                raise KeyError(required_key)
        return cls(
            model_name=mapping["model_name"],
            model_type=mapping["model_type"],
            parameters=mapping.get("parameters"),
        )

    def to_spice(self) -> str:
        if not self.parameters:
            return f".MODEL {self.model_name} {self.model_type}"
        return f".MODEL {self.model_name} {self.model_type}({_format_parameters(self.parameters)})"


@dataclass(frozen=True)
class XyceDeviceSpec:
    device_name: str
    nodes: tuple[str, ...]
    model_name: str | None = None
    parameters: Mapping[str, ConfigValue] | None = None
    expression: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "device_name", _validate_token(self.device_name, "device_name"))
        object.__setattr__(
            self,
            "nodes",
            _normalize_sequence(self.nodes, "nodes", allow_empty=False, token_items=True),
        )
        if self.model_name is not None:
            object.__setattr__(self, "model_name", _validate_token(self.model_name, "model_name"))
        object.__setattr__(self, "parameters", _normalize_parameters(self.parameters, "parameters"))
        object.__setattr__(
            self,
            "expression",
            _validate_optional_expression(self.expression, "expression"),
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceDeviceSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {"device_name", "nodes", "model_name", "parameters", "expression"},
            cls.__name__,
        )
        for required_key in ("device_name", "nodes"):
            if required_key not in mapping:
                raise KeyError(required_key)
        return cls(
            device_name=mapping["device_name"],
            nodes=mapping["nodes"],
            model_name=mapping.get("model_name"),
            parameters=mapping.get("parameters"),
            expression=mapping.get("expression"),
        )

    def to_spice(self) -> str:
        parts = [self.device_name, *self.nodes]
        if self.model_name is not None:
            parts.append(self.model_name)
        if self.parameters:
            parts.append(_format_parameters(self.parameters))
        if self.expression is not None:
            parts.append(self.expression)
        return " ".join(parts)


@dataclass(frozen=True)
class XyceOutputSpec:
    name: str
    analysis_type: str
    variables: tuple[str, ...]
    file: str
    output_format: str = "CSV"
    kind: OutputKind = "csv"
    required: bool = True
    directive: str = ".PRINT"

    def __post_init__(self):
        object.__setattr__(self, "name", _validate_non_empty_string(self.name, "name").strip())
        object.__setattr__(self, "analysis_type", _validate_analysis_type(self.analysis_type))
        object.__setattr__(
            self,
            "variables",
            _normalize_sequence(self.variables, "variables", allow_empty=False),
        )
        object.__setattr__(self, "file", validate_relative_output_path(self.file, "file"))
        object.__setattr__(
            self,
            "output_format",
            _validate_token(self.output_format, "output_format").upper(),
        )
        object.__setattr__(self, "kind", _normalize_report_kind(self.kind))
        object.__setattr__(self, "required", _normalize_boolean(self.required, "required"))
        object.__setattr__(
            self,
            "directive",
            _validate_directive_token(self.directive, "directive"),
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceOutputSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {
                "name",
                "analysis_type",
                "variables",
                "file",
                "output_format",
                "kind",
                "required",
                "directive",
            },
            cls.__name__,
        )
        for required_key in ("name", "analysis_type", "variables", "file"):
            if required_key not in mapping:
                raise KeyError(required_key)
        return cls(
            name=mapping["name"],
            analysis_type=mapping["analysis_type"],
            variables=mapping["variables"],
            file=mapping["file"],
            output_format=mapping.get("output_format", "CSV"),
            kind=mapping.get("kind", "csv"),
            required=mapping.get("required", True),
            directive=mapping.get("directive", ".PRINT"),
        )

    def to_spice(self) -> str:
        return (
            f"{self.directive} {self.analysis_type} FORMAT={self.output_format} "
            f"FILE={self.file} {' '.join(self.variables)}"
        )

    def output_spec(self) -> OutputSpec:
        return OutputSpec(
            name=self.name,
            path=self.file,
            kind=self.kind,
            required=self.required,
        )


@dataclass(frozen=True)
class XyceReportSpec:
    name: str
    path: str
    kind: ReportKind = "text"
    required: bool = True

    def __post_init__(self):
        object.__setattr__(self, "name", _validate_non_empty_string(self.name, "name").strip())
        object.__setattr__(self, "path", validate_relative_output_path(self.path, "path"))
        object.__setattr__(self, "kind", _normalize_report_kind(self.kind))
        object.__setattr__(self, "required", _normalize_boolean(self.required, "required"))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceReportSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(mapping, {"name", "path", "kind", "required"}, cls.__name__)
        for required_key in ("name", "path"):
            if required_key not in mapping:
                raise KeyError(required_key)
        return cls(
            name=mapping["name"],
            path=mapping["path"],
            kind=mapping.get("kind", "text"),
            required=mapping.get("required", True),
        )

    def output_spec(self) -> OutputSpec:
        return OutputSpec(
            name=self.name,
            path=self.path,
            kind=self.kind,
            required=self.required,
        )


@dataclass(frozen=True)
class XyceWorkflowResult:
    command: tuple[str, ...]
    working_dir: Path
    stdout: str
    stderr: str
    elapsed_sec: float
    outputs: Mapping[str, OutputArtifact] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "outputs", MappingProxyType(dict(self.outputs)))


@dataclass(frozen=True)
class XyceWorkflowSpec:
    executable: str
    arguments: tuple[str, ...] = field(default_factory=tuple)
    working_dir: Path | str | None = None
    expected_outputs: tuple[XyceReportSpec, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(
            self,
            "executable",
            _validate_non_empty_string(self.executable, "executable").strip(),
        )
        object.__setattr__(
            self,
            "arguments",
            _normalize_sequence(self.arguments, "arguments", allow_empty=True),
        )
        if self.working_dir is not None and not isinstance(self.working_dir, (str, Path)):
            raise TypeError("working_dir must be a string, Path, or None.")
        object.__setattr__(
            self,
            "expected_outputs",
            _normalize_spec_sequence(self.expected_outputs, "expected_outputs", XyceReportSpec),
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceWorkflowSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {"executable", "arguments", "working_dir", "expected_outputs"},
            cls.__name__,
        )
        if "executable" not in mapping:
            raise KeyError("executable")
        return cls(
            executable=mapping["executable"],
            arguments=mapping.get("arguments", ()),
            working_dir=mapping.get("working_dir"),
            expected_outputs=mapping.get("expected_outputs", ()),
        )

    def to_command(self) -> tuple[str, ...]:
        return (self.executable, *self.arguments)

    def run(self) -> XyceWorkflowResult:
        working_dir = _resolve_working_dir(self.working_dir)
        command = self.to_command()
        started_at = time.perf_counter()
        completed_process = subprocess.run(
            list(command),
            cwd=working_dir,
            capture_output=True,
            text=True,
        )
        elapsed_sec = time.perf_counter() - started_at

        if completed_process.returncode != 0:
            raise XyceWorkflowError(
                f"Xyce workflow failed (code {completed_process.returncode}).",
                command=command,
                returncode=completed_process.returncode,
                stdout=completed_process.stdout,
                stderr=completed_process.stderr,
                working_dir=working_dir,
                elapsed_sec=elapsed_sec,
            )

        outputs = collect_output_artifacts(
            working_dir,
            tuple(report.output_spec() for report in self.expected_outputs),
        )
        return XyceWorkflowResult(
            command=command,
            working_dir=working_dir,
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
            elapsed_sec=elapsed_sec,
            outputs=outputs,
        )


@dataclass(frozen=True)
class XdmWorkflowSpec(XyceWorkflowSpec):
    executable: str = "xdm"

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XdmWorkflowSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {"executable", "arguments", "working_dir", "expected_outputs"},
            cls.__name__,
        )
        return cls(
            executable=mapping.get("executable", "xdm"),
            arguments=mapping.get("arguments", ()),
            working_dir=mapping.get("working_dir"),
            expected_outputs=mapping.get("expected_outputs", ()),
        )


@dataclass(frozen=True)
class AdmsWorkflowSpec(XyceWorkflowSpec):
    executable: str = "admsXml"

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> AdmsWorkflowSpec:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {"executable", "arguments", "working_dir", "expected_outputs"},
            cls.__name__,
        )
        return cls(
            executable=mapping.get("executable", "admsXml"),
            arguments=mapping.get("arguments", ()),
            working_dir=mapping.get("working_dir"),
            expected_outputs=mapping.get("expected_outputs", ()),
        )


@dataclass(frozen=True)
class XyceFeatureConfig:
    directives: tuple[XyceDirectiveSpec, ...] = field(default_factory=tuple)
    models: tuple[XyceModelSpec, ...] = field(default_factory=tuple)
    devices: tuple[XyceDeviceSpec, ...] = field(default_factory=tuple)
    analyses: tuple[XyceAnalysisSpec, ...] = field(default_factory=tuple)
    outputs: tuple[XyceOutputSpec, ...] = field(default_factory=tuple)
    reports: tuple[XyceReportSpec, ...] = field(default_factory=tuple)
    workflows: tuple[XyceWorkflowSpec, ...] = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(
            self,
            "directives",
            _normalize_spec_sequence(self.directives, "directives", XyceDirectiveSpec),
        )
        object.__setattr__(
            self,
            "models",
            _normalize_spec_sequence(self.models, "models", XyceModelSpec),
        )
        object.__setattr__(
            self,
            "devices",
            _normalize_spec_sequence(self.devices, "devices", XyceDeviceSpec),
        )
        object.__setattr__(
            self,
            "analyses",
            _normalize_spec_sequence(self.analyses, "analyses", XyceAnalysisSpec),
        )
        object.__setattr__(
            self,
            "outputs",
            _normalize_spec_sequence(self.outputs, "outputs", XyceOutputSpec),
        )
        object.__setattr__(
            self,
            "reports",
            _normalize_spec_sequence(self.reports, "reports", XyceReportSpec),
        )
        object.__setattr__(
            self,
            "workflows",
            _normalize_workflow_sequence(self.workflows, "workflows"),
        )
        normalize_output_specs(self.output_specs())

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> XyceFeatureConfig:
        mapping = _require_mapping(mapping, cls.__name__)
        _reject_unknown_keys(
            mapping,
            {
                "directives",
                "models",
                "devices",
                "analyses",
                "outputs",
                "reports",
                "workflows",
            },
            cls.__name__,
        )
        return cls(
            directives=mapping.get("directives", ()),
            models=mapping.get("models", ()),
            devices=mapping.get("devices", ()),
            analyses=mapping.get("analyses", ()),
            outputs=mapping.get("outputs", ()),
            reports=mapping.get("reports", ()),
            workflows=mapping.get("workflows", ()),
        )

    def directive_lines(self) -> tuple[str, ...]:
        return tuple(
            spec.to_spice()
            for spec in (
                *self.directives,
                *self.models,
                *self.devices,
                *self.analyses,
                *self.outputs,
            )
        )

    def output_specs(self) -> tuple[OutputSpec, ...]:
        return tuple(
            spec.output_spec()
            for spec in (*self.outputs, *self.reports)
        )


def _normalize_workflow_sequence(values: object, field_name: str) -> tuple[XyceWorkflowSpec, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise TypeError(f"{field_name} must be a list or tuple.")

    normalized_values = []
    for value in values:
        if isinstance(value, XyceWorkflowSpec):
            normalized_values.append(value)
        elif isinstance(value, Mapping):
            normalized_values.append(XyceWorkflowSpec.from_mapping(value))
        else:
            raise TypeError(f"{field_name} items must be XyceWorkflowSpec instances or mappings.")
    return tuple(normalized_values)


def _resolve_working_dir(working_dir: Path | str | None) -> Path:
    if working_dir is None:
        return Path.cwd()
    path = Path(working_dir)
    if not path.exists():
        raise FileNotFoundError(f"working_dir does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"working_dir must be a directory: {path}")
    return path.resolve()


class XyceWorkflowError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        command: tuple[str, ...],
        returncode: int,
        stdout: str,
        stderr: str,
        working_dir: Path,
        elapsed_sec: float,
    ):
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.working_dir = working_dir
        self.elapsed_sec = elapsed_sec
