from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence, TextIO

from .engine import XyceRunError
from .netlists import XyceProject, XyceProjectResult
from .outputs import OutputArtifact, OutputSpec


def _extend_output_specs(
    output_specs: list[OutputSpec],
    entries: list[list[str]],
    *,
    kind: str,
    required: bool,
) -> None:
    for name, path in entries:
        if kind == "csv":
            output_specs.append(OutputSpec.csv(name, path, required=required))
        elif kind == "text":
            output_specs.append(OutputSpec.text(name, path, required=required))
        else:
            raise ValueError("kind must be exactly 'csv' or 'text'.")


def _build_output_specs(args: argparse.Namespace) -> tuple[OutputSpec, ...]:
    output_specs: list[OutputSpec] = []
    _extend_output_specs(output_specs, args.csv_output, kind="csv", required=True)
    _extend_output_specs(output_specs, args.text_output, kind="text", required=True)
    _extend_output_specs(output_specs, args.optional_csv_output, kind="csv", required=False)
    _extend_output_specs(output_specs, args.optional_text_output, kind="text", required=False)
    return tuple(output_specs)


def _summarize_output(artifact: OutputArtifact) -> dict[str, object]:
    summary: dict[str, object] = {
        "exists": artifact.exists,
        "kind": artifact.spec.kind,
        "path": str(artifact.path),
        "required": artifact.spec.required,
    }
    if artifact.frame is not None:
        summary["columns"] = list(artifact.frame.columns)
        summary["rows"] = len(artifact.frame)
    if artifact.text is not None:
        summary["characters"] = len(artifact.text)
    return summary


def _summarize_result(project: XyceProject, result: XyceProjectResult) -> dict[str, object]:
    return {
        "netlist_path": str(result.execution.netlist_path),
        "outputs": {
            name: _summarize_output(artifact)
            for name, artifact in result.outputs.items()
        },
        "project": project.name,
        "run_dir": str(result.run_dir),
        "solve_time_sec": result.solve_time_sec,
        "stderr": result.stderr,
        "stdout": result.stdout,
    }


def _run_command(args: argparse.Namespace, stdout: TextIO) -> int:
    project = XyceProject.from_file(
        args.netlist,
        name=args.name,
        output_specs=_build_output_specs(args),
    )
    result = project.run(
        xyce_path=args.xyce_path,
        base_out_dir=args.base_out_dir,
        run_name=args.run_name,
        target_dir=args.target_dir,
        keep_run_dir=not args.discard_run_dir,
    )
    print(json.dumps(_summarize_result(project, result), sort_keys=True), file=stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xyce-py", description="Run Xyce netlists through xyce-py.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run an exact Xyce netlist file.")
    run_parser.add_argument("netlist", type=Path, help="Path to the Xyce netlist file.")
    run_parser.add_argument("--name", help="Project name. Defaults to the netlist file stem.")
    run_parser.add_argument("--xyce-path", help="Path to the Xyce executable. Defaults to auto-detection.")
    run_parser.add_argument("--base-out-dir", default="_xyce_runs", help="Base output directory.")
    run_parser.add_argument("--run-name", help="Run directory name under --base-out-dir.")
    run_parser.add_argument("--target-dir", type=Path, help="Exact run directory. Overrides --base-out-dir.")
    run_parser.add_argument(
        "--discard-run-dir",
        action="store_true",
        help="Remove declared artifacts after parsing outputs.",
    )
    run_parser.add_argument(
        "--csv-output",
        action="append",
        default=[],
        metavar=("NAME", "PATH"),
        nargs=2,
        help="Declare a required CSV output file.",
    )
    run_parser.add_argument(
        "--text-output",
        action="append",
        default=[],
        metavar=("NAME", "PATH"),
        nargs=2,
        help="Declare a required text output file.",
    )
    run_parser.add_argument(
        "--optional-csv-output",
        action="append",
        default=[],
        metavar=("NAME", "PATH"),
        nargs=2,
        help="Declare an optional CSV output file.",
    )
    run_parser.add_argument(
        "--optional-text-output",
        action="append",
        default=[],
        metavar=("NAME", "PATH"),
        nargs=2,
        help="Declare an optional text output file.",
    )
    run_parser.set_defaults(command_handler=_run_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.command_handler(args, sys.stdout)
    except XyceRunError as exc:
        print(str(exc), file=sys.stderr)
        return exc.returncode or 1
