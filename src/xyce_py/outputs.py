from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

import pandas as pd

from ._validation import validate_non_empty_string as _validate_non_empty_string


OutputKind = Literal["csv", "text"]


def validate_relative_output_path(output_path: object, field_name: str) -> str:
    output_path = _validate_non_empty_string(output_path, field_name)
    path = Path(output_path)
    if path.is_absolute():
        raise ValueError(f"{field_name} must be a relative path inside the Xyce run directory.")
    if output_path == "." or not path.name:
        raise ValueError(f"{field_name} must point to a file inside the Xyce run directory.")
    if any(part == ".." for part in path.parts):
        raise ValueError(f"{field_name} cannot contain '..' path traversal.")
    return output_path


def read_csv_output(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


@dataclass(frozen=True)
class OutputSpec:
    name: str
    path: str
    kind: OutputKind = "csv"
    required: bool = True

    def __post_init__(self):
        name = _validate_non_empty_string(self.name, "name")
        path = validate_relative_output_path(self.path, "path")
        if self.kind not in {"csv", "text"}:
            raise ValueError("kind must be exactly 'csv' or 'text'.")
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "path", path)

    @classmethod
    def csv(cls, name: str, path: str, *, required: bool = True) -> OutputSpec:
        return cls(name=name, path=path, kind="csv", required=required)

    @classmethod
    def text(cls, name: str, path: str, *, required: bool = True) -> OutputSpec:
        return cls(name=name, path=path, kind="text", required=required)

    def resolve_path(self, run_dir: Path) -> Path:
        return Path(run_dir) / self.path


@dataclass(frozen=True)
class OutputArtifact:
    spec: OutputSpec
    path: Path
    exists: bool
    frame: pd.DataFrame | None = None
    text: str | None = None


def normalize_output_specs(output_specs: Iterable[OutputSpec]) -> tuple[OutputSpec, ...]:
    specs = tuple(output_specs)
    seen_names: set[str] = set()
    for spec in specs:
        if not isinstance(spec, OutputSpec):
            raise TypeError("output_specs must contain only OutputSpec instances.")
        if spec.name in seen_names:
            raise ValueError(f"Duplicate output spec name: {spec.name!r}.")
        seen_names.add(spec.name)
    return specs


def load_output_artifact(run_dir: Path, spec: OutputSpec) -> OutputArtifact:
    if not isinstance(spec, OutputSpec):
        raise TypeError("spec must be an OutputSpec instance.")

    output_path = spec.resolve_path(run_dir)
    if not output_path.exists():
        if spec.required:
            raise FileNotFoundError(
                f"Required Xyce output {spec.name!r} was not produced at {output_path}."
            )
        return OutputArtifact(spec=spec, path=output_path, exists=False)

    if spec.kind == "csv":
        return OutputArtifact(
            spec=spec,
            path=output_path,
            exists=True,
            frame=read_csv_output(output_path),
        )

    return OutputArtifact(
        spec=spec,
        path=output_path,
        exists=True,
        text=output_path.read_text(),
    )


def collect_output_artifacts(
    run_dir: Path,
    output_specs: Iterable[OutputSpec],
) -> Mapping[str, OutputArtifact]:
    specs = normalize_output_specs(output_specs)
    artifacts = {
        spec.name: load_output_artifact(run_dir, spec)
        for spec in specs
    }
    return MappingProxyType(artifacts)
