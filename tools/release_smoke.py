from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import sys

EXPECTED_EXPORTS = {
    "CircuitGraph",
    "NetlistCompiler",
    "MonteCarloParameter",
    "NormalDistribution",
    "OptionsDirective",
    "OutputSpec",
    "ParameterDirective",
    "RawNTerminalDevice",
    "RawTwoTerminalElement",
    "parse_measurements",
    "Resistor",
    "SweepParameter",
    "UniformDistribution",
    "XdmTranslator",
    "XyceMonteCarloSweep",
    "VoltageSource",
    "XyceParameterSweep",
    "XyceProject",
    "find_xyce_executable",
}


def build_compile_only_netlist(package_module) -> str:
    circuit = package_module.CircuitGraph(xyce_path="Xyce")
    circuit.add_node("gnd", is_ground=True)
    circuit.add_branch("vin", "gnd", [package_module.VoltageSource("supply", 5.0)])
    circuit.add_branch("vin", "vout", [package_module.Resistor("r1", 1000)])
    circuit.add_branch("vout", "gnd", [package_module.Resistor("r2", 1000)])
    return package_module.NetlistCompiler(circuit.G, circuit.spice_directives).compile()


def build_raw_netlist_project(package_module):
    return package_module.XyceProject(
        "raw-smoke",
        "* raw smoke\nR1 1 0 1k\n.OP\n.PRINT DC FORMAT=CSV FILE=raw.csv V(1)\n.END\n",
        output_specs=(package_module.OutputSpec.csv("waveforms", "raw.csv"),),
    )


def run_smoke(expect_version: str | None = None) -> dict[str, object]:
    import xyce_py
    import xyce_py.cli

    package_version = metadata.version("xyce-py")
    if expect_version is not None and package_version != expect_version:
        raise AssertionError(
            f"Installed xyce-py version {package_version!r} did not match expected version {expect_version!r}."
        )

    missing_exports = sorted(EXPECTED_EXPORTS - set(xyce_py.__all__))
    if missing_exports:
        raise AssertionError(f"xyce_py.__all__ is missing expected exports: {missing_exports!r}.")

    for name in EXPECTED_EXPORTS:
        if getattr(xyce_py, name, None) is None:
            raise AssertionError(f"xyce_py.{name} did not resolve to an object.")
    if xyce_py.cli.main is None:
        raise AssertionError("xyce_py.cli.main did not resolve to an object.")

    package_metadata = metadata.metadata("xyce-py")
    netlist = build_compile_only_netlist(xyce_py)
    if not netlist.startswith("* Generated Circuit\n"):
        raise AssertionError("Compile-only smoke netlist did not start with the generated-circuit header.")
    if not netlist.endswith(".END\n"):
        raise AssertionError("Compile-only smoke netlist did not end with a single trailing .END line.")

    raw_project = build_raw_netlist_project(xyce_py)
    if raw_project.output_specs[0].path != "raw.csv":
        raise AssertionError("Raw-project smoke did not preserve the declared output path.")

    raw_element_line = xyce_py.RawTwoTerminalElement(
        "load",
        "R_$name $node_pos $node_neg 1k",
    ).to_spice("N_1", "0")
    if raw_element_line != "R_load N_1 0 1k":
        raise AssertionError("RawTwoTerminalElement smoke did not emit the expected element line.")

    raw_device_line = xyce_py.RawNTerminalDevice(
        "amp",
        "AMP_MODEL",
        terminals=2,
        template="X_$name $n0 $n1 $model_name",
    ).to_spice(["N_1", "N_2"])
    if raw_device_line != "X_amp N_1 N_2 AMP_MODEL":
        raise AssertionError("RawNTerminalDevice smoke did not emit the expected device line.")

    xdm_translator = xyce_py.XdmTranslator("xdm")
    if xdm_translator.xdm_path != "xdm":
        raise AssertionError("XdmTranslator smoke did not preserve the declared executable path.")

    sweep = xyce_py.XyceParameterSweep(
        "smoke-sweep",
        "* smoke sweep\nR1 1 0 {RLOAD}\n.OP\n.PRINT DC FORMAT=CSV FILE=raw.csv V(1)\n.END\n",
        parameters=(xyce_py.SweepParameter("RLOAD", ["1k", "2k"]),),
        output_specs=(xyce_py.OutputSpec.csv("waveforms", "raw.csv"),),
    )
    if len(sweep.points()) != 2:
        raise AssertionError("Parameter sweep smoke did not produce the expected point count.")

    monte_carlo = xyce_py.XyceMonteCarloSweep(
        "smoke-monte-carlo",
        "* smoke mc\nR1 1 0 {RLOAD}\n.OP\n.PRINT DC FORMAT=CSV FILE=raw.csv V(1)\n.END\n",
        parameters=(xyce_py.MonteCarloParameter("RLOAD", xyce_py.UniformDistribution(1_000, 2_000)),),
        samples=2,
        seed=1,
        output_specs=(xyce_py.OutputSpec.csv("waveforms", "raw.csv"),),
    )
    if len(monte_carlo.points()) != 2:
        raise AssertionError("Monte Carlo smoke did not produce the expected point count.")

    parameter_line = xyce_py.ParameterDirective("RLOAD", "1k").to_spice()
    if parameter_line != ".PARAM RLOAD=1k":
        raise AssertionError("ParameterDirective smoke did not emit the expected .PARAM line.")

    options_line = xyce_py.OptionsDirective("NONLIN", {"RELTOL": "1e-4"}).to_spice()
    if options_line != ".OPTIONS NONLIN RELTOL=1e-4":
        raise AssertionError("OptionsDirective smoke did not emit the expected .OPTIONS line.")

    measurements = xyce_py.parse_measurements("GAIN = 5.000000e-01\n")
    if measurements["GAIN"].value != 0.5:
        raise AssertionError("Measurement parser smoke did not parse the expected numeric value.")

    return {
        "package_name": package_metadata["Name"],
        "package_version": package_version,
        "summary": package_metadata["Summary"],
        "required_python": package_metadata["Requires-Python"],
        "export_count": len(xyce_py.__all__),
        "has_cli": True,
        "netlist_line_count": len(netlist.splitlines()),
        "options_directive": options_line,
        "parameter_directive": parameter_line,
        "parsed_measurements": len(measurements),
        "raw_project_outputs": len(raw_project.output_specs),
        "monte_carlo_points": len(monte_carlo.points()),
        "sweep_points": len(sweep.points()),
        "xdm_path": xdm_translator.xdm_path,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the standalone installed-package smoke checks for xyce-py.")
    parser.add_argument(
        "--expect-version",
        help="Optional exact version string that must match the installed xyce-py distribution.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        smoke_result = run_smoke(expect_version=args.expect_version)
    except Exception as exc:  # pragma: no cover - exercised through subprocess tests
        print(f"release smoke failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(smoke_result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
