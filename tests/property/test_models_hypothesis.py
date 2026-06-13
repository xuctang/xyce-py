from __future__ import annotations

import math
import string

import pytest
from hypothesis import given, strategies as st

from xyce_py.models import Resistor


pytestmark = pytest.mark.property


VALID_NAME = st.text(
    alphabet=string.ascii_letters + string.digits + "_",
    min_size=1,
    max_size=20,
).filter(lambda value: bool(value.strip()))


INVALID_NAME = st.one_of(
    st.none(),
    st.integers(),
    st.booleans(),
    st.text(alphabet=" \t\n", min_size=1, max_size=5),
)


VALUE_LIKE = st.one_of(
    st.floats(allow_nan=False, allow_infinity=False, width=32),
    st.text(
        alphabet=string.ascii_letters + string.digits + "._+-",
        min_size=1,
        max_size=12,
    ).filter(lambda value: bool(value.strip())),
)


@given(name=VALID_NAME)
def test_valid_names_round_trip_under_hypothesis(name):
    resistor = Resistor(name, "1k")

    assert resistor.name == name
    assert resistor.to_spice("n1", "0").startswith(f"R_{name} ")


@given(name=INVALID_NAME)
def test_invalid_names_are_rejected_under_hypothesis(name):
    with pytest.raises((TypeError, ValueError)):
        Resistor(name, "1k")


@given(value=VALUE_LIKE)
def test_value_like_validation_accepts_expected_domains_under_hypothesis(value):
    resistor = Resistor("r1", value)
    spice_line = resistor.to_spice("n1", "0")

    if isinstance(value, str):
        assert spice_line.endswith(f" {value}")
    else:
        assert math.isclose(resistor.value, float(value))
        assert spice_line.endswith(f" {float(value)}")
