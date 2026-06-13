from __future__ import annotations

import pytest

from xyce_py.directives import (
    MeasureDirective,
    ParameterDirective,
    PrintDirective,
    RawDirective,
)
from xyce_py.compiler import NetlistCompiler
from xyce_py.graph import CircuitGraph
from xyce_py.models import Resistor, VoltageSource


pytestmark = pytest.mark.unit


def test_parameter_directive_emits_exact_param_line_for_numeric_and_string_values():
    assert ParameterDirective("RLOAD", 1000).to_spice() == ".PARAM RLOAD=1000.0"
    assert ParameterDirective("tau_1", "1u").to_spice() == ".PARAM tau_1=1u"


@pytest.mark.parametrize("bad_name", ["", " ", "1bad", "bad-name", "bad.name", None, 3])
def test_parameter_directive_rejects_invalid_names(bad_name):
    with pytest.raises((TypeError, ValueError)):
        ParameterDirective(bad_name, 1)


@pytest.mark.parametrize("bad_value", ["", " ", None, True, object()])
def test_parameter_directive_rejects_invalid_values(bad_value):
    with pytest.raises((TypeError, ValueError)):
        ParameterDirective("RLOAD", bad_value)


def test_print_directive_emits_csv_file_print_line():
    directive = PrintDirective("dc", ["V(1)", "I(V1)"], file="nested/output.csv")

    assert directive.to_spice() == ".PRINT DC FORMAT=CSV FILE=nested/output.csv V(1) I(V1)"


@pytest.mark.parametrize("analysis_type", ["", " ", ".DC", None, 3])
def test_print_directive_rejects_invalid_analysis_types(analysis_type):
    with pytest.raises((TypeError, ValueError)):
        PrintDirective(analysis_type, ["V(1)"])


@pytest.mark.parametrize("variables", [[], (), "V(1)", ["V(1)", ""], ["V(1)", 3]])
def test_print_directive_rejects_invalid_variables(variables):
    with pytest.raises((TypeError, ValueError)):
        PrintDirective("DC", variables)


@pytest.mark.parametrize("bad_file", ["", " ", ".", "../output.csv", "/tmp/output.csv"])
def test_print_directive_rejects_invalid_output_file_paths(bad_file):
    with pytest.raises(ValueError):
        PrintDirective("DC", ["V(1)"], file=bad_file)


def test_print_directive_accepts_only_csv_output_format():
    with pytest.raises(ValueError, match="output_format must be exactly 'CSV'"):
        PrintDirective("DC", ["V(1)"], output_format="RAW")


def test_measure_directive_preserves_expression_text():
    directive = MeasureDirective(
        "tran",
        "rise_time",
        "TRIG V(out) VAL=0.1 RISE=1 TARG V(out) VAL=0.9 RISE=1",
    )

    assert (
        directive.to_spice()
        == ".MEASURE TRAN rise_time TRIG V(out) VAL=0.1 RISE=1 TARG V(out) VAL=0.9 RISE=1"
    )


@pytest.mark.parametrize("bad_expression", ["", " ", None, 3])
def test_measure_directive_rejects_invalid_expression(bad_expression):
    with pytest.raises((TypeError, ValueError)):
        MeasureDirective("TRAN", "rise_time", bad_expression)


def test_raw_directive_preserves_opaque_directive_text_after_outer_validation():
    directive = RawDirective("  .NOISE V(out) V1 DEC 10 1 1e6  ")

    assert directive.to_spice() == ".NOISE V(out) V1 DEC 10 1 1e6"


@pytest.mark.parametrize("bad_text", ["", " ", "R1 1 0 1k", None, 3])
def test_raw_directive_rejects_invalid_outer_directive_text(bad_text):
    with pytest.raises((TypeError, ValueError)):
        RawDirective(bad_text)


def test_circuit_graph_add_parameter_appends_param_directive_before_compiled_elements():
    circuit = CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_parameter("RLOAD", "1k")
    circuit.add_branch("vin", "gnd", [VoltageSource("src", 5.0)])
    circuit.add_branch("vin", "gnd", [Resistor("load", "{RLOAD}")])

    netlist = NetlistCompiler(circuit.G, circuit.spice_directives).compile()

    assert ".PARAM RLOAD=1k" in netlist
    assert netlist.index(".PARAM RLOAD=1k") < netlist.index("V_src")


def test_circuit_graph_add_parameter_uses_parameter_directive_contract():
    circuit = CircuitGraph(xyce_path="Xyce")

    with pytest.raises(ValueError, match="name must be a SPICE identifier"):
        circuit.add_parameter("bad-name", "1k")
