from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ._validation import validate_non_empty_string as _validate_non_empty_string


@dataclass(frozen=True)
class MeasurementResult:
    name: str
    value_text: str
    value: float | None

    def __post_init__(self):
        object.__setattr__(self, "name", _validate_non_empty_string(self.name, "name"))
        object.__setattr__(self, "value_text", _validate_non_empty_string(self.value_text, "value_text"))
        if self.value is not None and (isinstance(self.value, bool) or not isinstance(self.value, float)):
            raise TypeError("value must be a float or None.")


def _parse_measurement_value(value_text: str) -> float | None:
    try:
        return float(value_text)
    except ValueError:
        return None


def parse_measurements(measurement_text: str) -> Mapping[str, MeasurementResult]:
    if not isinstance(measurement_text, str):
        raise TypeError("measurement_text must be a string.")

    measurements: dict[str, MeasurementResult] = {}
    for line_number, line in enumerate(measurement_text.splitlines(), start=1):
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith("*"):
            continue
        if "=" not in stripped_line:
            raise ValueError(f"Measurement line {line_number} must contain '='.")

        name, value_text = (part.strip() for part in stripped_line.split("=", maxsplit=1))
        name = _validate_non_empty_string(name, f"measurement line {line_number} name")
        value_text = _validate_non_empty_string(value_text, f"measurement line {line_number} value")
        if name in measurements:
            raise ValueError(f"Duplicate measurement name: {name!r}.")
        measurements[name] = MeasurementResult(
            name=name,
            value_text=value_text,
            value=_parse_measurement_value(value_text),
        )

    return MappingProxyType(measurements)


def read_measurements(path: Path | str) -> Mapping[str, MeasurementResult]:
    return parse_measurements(Path(path).read_text())
