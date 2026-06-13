from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import product
import random
import re
from pathlib import Path
from types import MappingProxyType

from ._validation import validate_non_empty_string as _validate_non_empty_string
from .directives import DirectiveValue, ParameterDirective
from .netlists import XyceProject, XyceProjectResult
from .outputs import OutputSpec, normalize_output_specs


_PARAM_ASSIGNMENT_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _validate_sweep_index(index: object) -> int:
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("index must be an integer.")
    if index < 0:
        raise ValueError("index must be non-negative.")
    return index


def _existing_param_names(netlist_content: str) -> set[str]:
    existing_names: set[str] = set()
    for line in netlist_content.splitlines():
        stripped_line = line.strip()
        if not stripped_line:
            continue
        first_token = stripped_line.split(maxsplit=1)[0].upper()
        if first_token != ".PARAM":
            continue
        existing_names.update(name.upper() for name in _PARAM_ASSIGNMENT_PATTERN.findall(stripped_line))
    return existing_names


def _normalize_sweep_parameters(parameters: Iterable[SweepParameter]) -> tuple[SweepParameter, ...]:
    parameters = tuple(parameters)
    if not parameters:
        raise ValueError("parameters must be a non-empty sequence.")
    if not all(isinstance(parameter, SweepParameter) for parameter in parameters):
        raise TypeError("parameters must contain only SweepParameter instances.")

    seen_names: set[str] = set()
    for parameter in parameters:
        parameter_name = parameter.name.upper()
        if parameter_name in seen_names:
            raise ValueError(f"Duplicate sweep parameter name: {parameter.name!r}.")
        seen_names.add(parameter_name)
    return parameters


def _reject_existing_param_conflicts(netlist_content: str, parameter_names: Iterable[str]) -> None:
    requested_names = {parameter_name.upper() for parameter_name in parameter_names}
    conflicting_names = requested_names & _existing_param_names(netlist_content)
    if conflicting_names:
        raise ValueError(
            "Sweep parameter names must not already be defined by .PARAM lines: "
            + ", ".join(sorted(conflicting_names))
        )


def _validate_numeric_value(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    return float(value)


def _validate_positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return value


def _insert_parameter_directives(
    netlist_content: str,
    parameters: Mapping[str, str],
) -> str:
    lines = netlist_content.splitlines()
    parameter_lines = [
        ParameterDirective(name, value).to_spice()
        for name, value in parameters.items()
    ]
    variant_lines = [lines[0], *parameter_lines, *lines[1:]]
    variant_netlist = "\n".join(variant_lines)
    if netlist_content.endswith("\n"):
        variant_netlist += "\n"
    return variant_netlist


def _run_sweep_points(
    *,
    name: str,
    netlist_content: str,
    output_specs: tuple[OutputSpec, ...],
    points: tuple[SweepPoint, ...],
    xyce_path: str | None,
    base_out_dir: Path | str,
    run_name: str | None,
    keep_run_dirs: bool,
) -> XyceParameterSweepResult:
    if run_name is not None:
        run_name = _validate_non_empty_string(run_name, "run_name")
    if not isinstance(keep_run_dirs, bool):
        raise TypeError("keep_run_dirs must be a boolean.")

    base_run_name = run_name or name
    runs: list[SweepRunResult] = []
    for point in points:
        point_run_name = f"{base_run_name}_{point.index:04d}"
        project = XyceProject(
            point_run_name,
            _insert_parameter_directives(netlist_content, point.parameters),
            output_specs,
        )
        runs.append(
            SweepRunResult(
                point=point,
                result=project.run(
                    xyce_path=xyce_path,
                    base_out_dir=base_out_dir,
                    run_name=point_run_name,
                    keep_run_dir=keep_run_dirs,
                ),
            )
        )
    return XyceParameterSweepResult(name=name, runs=tuple(runs))


@dataclass(frozen=True)
class SweepParameter:
    name: str
    values: tuple[str, ...]

    def __init__(self, name: str, values: list[DirectiveValue]):
        if not isinstance(values, list):
            raise TypeError("values must be provided as a list.")
        if not values:
            raise ValueError("values must be a non-empty list.")
        normalized_values = tuple(
            ParameterDirective(name, value).value
            for value in values
        )
        object.__setattr__(self, "name", ParameterDirective(name, normalized_values[0]).name)
        object.__setattr__(self, "values", normalized_values)


@dataclass(frozen=True)
class UniformDistribution:
    low: float
    high: float

    def __post_init__(self):
        low = _validate_numeric_value(self.low, "low")
        high = _validate_numeric_value(self.high, "high")
        if high <= low:
            raise ValueError("high must be greater than low.")
        object.__setattr__(self, "low", low)
        object.__setattr__(self, "high", high)

    def sample(self, rng: random.Random) -> float:
        return rng.uniform(self.low, self.high)


@dataclass(frozen=True)
class NormalDistribution:
    mean: float
    stddev: float

    def __post_init__(self):
        mean = _validate_numeric_value(self.mean, "mean")
        stddev = _validate_numeric_value(self.stddev, "stddev")
        if stddev <= 0:
            raise ValueError("stddev must be positive.")
        object.__setattr__(self, "mean", mean)
        object.__setattr__(self, "stddev", stddev)

    def sample(self, rng: random.Random) -> float:
        return rng.gauss(self.mean, self.stddev)


@dataclass(frozen=True)
class MonteCarloParameter:
    name: str
    distribution: UniformDistribution | NormalDistribution

    def __post_init__(self):
        name = ParameterDirective(self.name, 0).name
        if not isinstance(self.distribution, (UniformDistribution, NormalDistribution)):
            raise TypeError("distribution must be a UniformDistribution or NormalDistribution.")
        object.__setattr__(self, "name", name)


@dataclass(frozen=True)
class SweepPoint:
    index: int
    parameters: Mapping[str, str]

    def __post_init__(self):
        index = _validate_sweep_index(self.index)
        if not isinstance(self.parameters, Mapping):
            raise TypeError("parameters must be a mapping.")
        if not self.parameters:
            raise ValueError("parameters must be a non-empty mapping.")
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True)
class SweepRunResult:
    point: SweepPoint
    result: XyceProjectResult


@dataclass(frozen=True)
class XyceParameterSweepResult:
    name: str
    runs: tuple[SweepRunResult, ...]

    def __post_init__(self):
        object.__setattr__(self, "name", _validate_non_empty_string(self.name, "name"))
        runs = tuple(self.runs)
        if not runs:
            raise ValueError("runs must be a non-empty sequence.")
        object.__setattr__(self, "runs", runs)

    def run(self, index: int) -> SweepRunResult:
        index = _validate_sweep_index(index)
        for sweep_run in self.runs:
            if sweep_run.point.index == index:
                return sweep_run
        raise KeyError(index)


@dataclass(frozen=True)
class XyceParameterSweep:
    name: str
    netlist_content: str
    parameters: tuple[SweepParameter, ...]
    output_specs: tuple[OutputSpec, ...] = ()

    def __post_init__(self):
        name = _validate_non_empty_string(self.name, "name")
        base_project = XyceProject(name, self.netlist_content, self.output_specs)
        parameters = _normalize_sweep_parameters(self.parameters)
        _reject_existing_param_conflicts(base_project.netlist_content, [parameter.name for parameter in parameters])

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "netlist_content", base_project.netlist_content)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "output_specs", normalize_output_specs(base_project.output_specs))

    @classmethod
    def from_file(
        cls,
        path: Path | str,
        *,
        parameters: Iterable[SweepParameter],
        output_specs: Iterable[OutputSpec] = (),
        name: str | None = None,
    ) -> XyceParameterSweep:
        netlist_path = Path(path)
        project_name = name if name is not None else netlist_path.stem
        return cls(
            name=project_name,
            netlist_content=netlist_path.read_text(),
            parameters=tuple(parameters),
            output_specs=tuple(output_specs),
        )

    def points(self) -> tuple[SweepPoint, ...]:
        parameter_names = [parameter.name for parameter in self.parameters]
        value_products = product(*(parameter.values for parameter in self.parameters))
        return tuple(
            SweepPoint(index=index, parameters=dict(zip(parameter_names, values)))
            for index, values in enumerate(value_products)
        )

    def netlist_for_point(self, point: SweepPoint) -> str:
        if not isinstance(point, SweepPoint):
            raise TypeError("point must be a SweepPoint instance.")
        return _insert_parameter_directives(self.netlist_content, point.parameters)

    def run(
        self,
        *,
        xyce_path: str | None = None,
        base_out_dir: Path | str = "_xyce_runs",
        run_name: str | None = None,
        keep_run_dirs: bool = True,
    ) -> XyceParameterSweepResult:
        return _run_sweep_points(
            name=self.name,
            netlist_content=self.netlist_content,
            output_specs=self.output_specs,
            points=self.points(),
            xyce_path=xyce_path,
            base_out_dir=base_out_dir,
            run_name=run_name,
            keep_run_dirs=keep_run_dirs,
        )


@dataclass(frozen=True)
class XyceMonteCarloSweep:
    name: str
    netlist_content: str
    parameters: tuple[MonteCarloParameter, ...]
    samples: int
    seed: int = 0
    output_specs: tuple[OutputSpec, ...] = ()

    def __post_init__(self):
        name = _validate_non_empty_string(self.name, "name")
        base_project = XyceProject(name, self.netlist_content, self.output_specs)
        samples = _validate_positive_integer(self.samples, "samples")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise TypeError("seed must be an integer.")

        parameters = tuple(self.parameters)
        if not parameters:
            raise ValueError("parameters must be a non-empty sequence.")
        if not all(isinstance(parameter, MonteCarloParameter) for parameter in parameters):
            raise TypeError("parameters must contain only MonteCarloParameter instances.")

        seen_names: set[str] = set()
        for parameter in parameters:
            parameter_name = parameter.name.upper()
            if parameter_name in seen_names:
                raise ValueError(f"Duplicate Monte Carlo parameter name: {parameter.name!r}.")
            seen_names.add(parameter_name)
        _reject_existing_param_conflicts(base_project.netlist_content, [parameter.name for parameter in parameters])

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "netlist_content", base_project.netlist_content)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "output_specs", normalize_output_specs(base_project.output_specs))

    def points(self) -> tuple[SweepPoint, ...]:
        rng = random.Random(self.seed)
        points: list[SweepPoint] = []
        for index in range(self.samples):
            point_parameters: dict[str, str] = {}
            for parameter in self.parameters:
                sampled_value = parameter.distribution.sample(rng)
                point_parameters[parameter.name] = ParameterDirective(parameter.name, sampled_value).value
            points.append(SweepPoint(index=index, parameters=point_parameters))
        return tuple(points)

    def netlist_for_point(self, point: SweepPoint) -> str:
        if not isinstance(point, SweepPoint):
            raise TypeError("point must be a SweepPoint instance.")
        return _insert_parameter_directives(self.netlist_content, point.parameters)

    def run(
        self,
        *,
        xyce_path: str | None = None,
        base_out_dir: Path | str = "_xyce_runs",
        run_name: str | None = None,
        keep_run_dirs: bool = True,
    ) -> XyceParameterSweepResult:
        return _run_sweep_points(
            name=self.name,
            netlist_content=self.netlist_content,
            output_specs=self.output_specs,
            points=self.points(),
            xyce_path=xyce_path,
            base_out_dir=base_out_dir,
            run_name=run_name,
            keep_run_dirs=keep_run_dirs,
        )
