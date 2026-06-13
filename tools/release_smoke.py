from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import sys

EXPECTED_EXPORTS = {
    "CircuitGraph",
    "NetlistCompiler",
    "OutputSpec",
    "Resistor",
    "VoltageSource",
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

    package_metadata = metadata.metadata("xyce-py")
    netlist = build_compile_only_netlist(xyce_py)
    if not netlist.startswith("* Generated Circuit\n"):
        raise AssertionError("Compile-only smoke netlist did not start with the generated-circuit header.")
    if not netlist.endswith(".END\n"):
        raise AssertionError("Compile-only smoke netlist did not end with a single trailing .END line.")

    raw_project = build_raw_netlist_project(xyce_py)
    if raw_project.output_specs[0].path != "raw.csv":
        raise AssertionError("Raw-project smoke did not preserve the declared output path.")

    return {
        "package_name": package_metadata["Name"],
        "package_version": package_version,
        "summary": package_metadata["Summary"],
        "required_python": package_metadata["Requires-Python"],
        "export_count": len(xyce_py.__all__),
        "netlist_line_count": len(netlist.splitlines()),
        "raw_project_outputs": len(raw_project.output_specs),
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
