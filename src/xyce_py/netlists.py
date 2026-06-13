from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ._validation import validate_non_empty_string as _validate_non_empty_string
from .engine import XyceExecutionResult, find_xyce_executable, run_xyce_netlist
from .outputs import (
    OutputArtifact,
    OutputSpec,
    collect_output_artifacts,
    normalize_output_specs,
)


def _netlist_has_end(netlist_content: str) -> bool:
    for line in netlist_content.splitlines():
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("*"):
            continue
        token = stripped_line.split(maxsplit=1)[0].upper()
        if token == ".END":
            return True
    return False


def _validate_raw_netlist_content(netlist_content: object) -> str:
    netlist_content = _validate_non_empty_string(netlist_content, "netlist_content")
    if not _netlist_has_end(netlist_content):
        raise ValueError("netlist_content must contain a top-level '.END' line.")
    return netlist_content


def _first_csv_output_path(output_specs: tuple[OutputSpec, ...]) -> str:
    for spec in output_specs:
        if spec.kind == "csv":
            return spec.path
    return "output.csv"


def _cleanup_project_artifacts(
    execution: XyceExecutionResult,
    output_specs: tuple[OutputSpec, ...],
) -> None:
    artifact_paths = {execution.netlist_path}
    for spec in output_specs:
        output_path = spec.resolve_path(execution.run_dir)
        artifact_paths.add(output_path)
        if spec.kind == "csv":
            artifact_paths.add(output_path.with_suffix(".prn"))

    for artifact_path in artifact_paths:
        artifact_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class XyceProjectResult:
    execution: XyceExecutionResult
    outputs: Mapping[str, OutputArtifact]

    def __post_init__(self):
        object.__setattr__(self, "outputs", MappingProxyType(dict(self.outputs)))

    @property
    def run_dir(self) -> Path:
        return self.execution.run_dir

    @property
    def stdout(self) -> str:
        return self.execution.stdout

    @property
    def stderr(self) -> str:
        return self.execution.stderr

    @property
    def solve_time_sec(self) -> float:
        return self.execution.solve_time_sec

    def output(self, name: str) -> OutputArtifact:
        name = _validate_non_empty_string(name, "name")
        return self.outputs[name]


@dataclass(frozen=True)
class XyceProject:
    name: str
    netlist_content: str
    output_specs: tuple[OutputSpec, ...] = ()

    def __post_init__(self):
        name = _validate_non_empty_string(self.name, "name")
        netlist_content = _validate_raw_netlist_content(self.netlist_content)
        output_specs = normalize_output_specs(self.output_specs)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "netlist_content", netlist_content)
        object.__setattr__(self, "output_specs", output_specs)

    @classmethod
    def from_file(
        cls,
        path: Path | str,
        *,
        output_specs: Iterable[OutputSpec] = (),
        name: str | None = None,
    ) -> XyceProject:
        netlist_path = Path(path)
        project_name = name if name is not None else netlist_path.stem
        return cls(
            name=project_name,
            netlist_content=netlist_path.read_text(),
            output_specs=tuple(output_specs),
        )

    def run(
        self,
        *,
        xyce_path: str | None = None,
        base_out_dir: Path | str = "_xyce_runs",
        run_name: str | None = None,
        target_dir: Path | None = None,
        keep_run_dir: bool = True,
    ) -> XyceProjectResult:
        if run_name is not None:
            run_name = _validate_non_empty_string(run_name, "run_name")
        if not isinstance(keep_run_dir, bool):
            raise TypeError("keep_run_dir must be a boolean.")

        execution = run_xyce_netlist(
            xyce_path=xyce_path or find_xyce_executable(),
            base_out_dir=base_out_dir,
            netlist_content=self.netlist_content,
            csv_name=_first_csv_output_path(self.output_specs),
            run_name=run_name or self.name,
            target_dir=target_dir,
            keep_run_dir=True,
        )
        outputs = collect_output_artifacts(execution.run_dir, self.output_specs)
        if not keep_run_dir:
            _cleanup_project_artifacts(execution, self.output_specs)
        return XyceProjectResult(execution=execution, outputs=outputs)
