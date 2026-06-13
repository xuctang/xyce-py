from __future__ import annotations

from types import MappingProxyType

import pytest

from xyce_py.measurements import MeasurementResult, parse_measurements, read_measurements


pytestmark = pytest.mark.unit


def test_parse_measurements_returns_read_only_named_results():
    measurements = parse_measurements(
        """
* comment
MAX_OUT = 1.189859e-02
STATUS = FAILED
"""
    )

    assert isinstance(measurements, MappingProxyType)
    assert measurements["MAX_OUT"] == MeasurementResult(
        name="MAX_OUT",
        value_text="1.189859e-02",
        value=0.01189859,
    )
    assert measurements["STATUS"] == MeasurementResult(
        name="STATUS",
        value_text="FAILED",
        value=None,
    )
    with pytest.raises(TypeError):
        measurements["NEW"] = MeasurementResult("NEW", "1", 1.0)


@pytest.mark.parametrize(
    "measurement_text",
    [
        "MAX_OUT 1.0\n",
        "= 1.0\n",
        "MAX_OUT = \n",
        "MAX_OUT = 1.0\nMAX_OUT = 2.0\n",
    ],
)
def test_parse_measurements_rejects_malformed_measurement_lines(measurement_text):
    with pytest.raises(ValueError):
        parse_measurements(measurement_text)


def test_parse_measurements_rejects_non_string_input():
    with pytest.raises(TypeError, match="measurement_text must be a string"):
        parse_measurements(None)


def test_measurement_result_rejects_non_float_numeric_value():
    with pytest.raises(TypeError, match="value must be a float or None"):
        MeasurementResult("MAX_OUT", "1", 1)


def test_read_measurements_reads_measurement_file(tmp_path):
    measurement_path = tmp_path / "circuit.cir.mt0"
    measurement_path.write_text("GAIN = 5.000000e-01\n")

    measurements = read_measurements(measurement_path)

    assert measurements["GAIN"].value == 0.5
