# xyce-py Testing Matrix

This matrix maps wrapper-owned failure classes to automated tests. Xyce simulator semantics are not revalidated here; those remain Xyce-owned. `xyce-py` tests pass-through behavior, generated netlist text, output collection, and structured error surfacing at those boundaries.

| Area | Failure classes covered | Primary tests |
| --- | --- | --- |
| Public API and packaging | missing exports, stale package metadata, missing CLI entry point, missing `py.typed`, stale wheel/sdist contents | `tests/unit/test_api_contract.py`, `tests/packaging/test_installed_package.py`, `tests/unit/test_release_smoke.py` |
| CLI | bad output declaration kind, text output summaries, Xyce failures, target-dir/discard controls, `python -m xyce_py` exit behavior | `tests/unit/test_cli.py`, `tests/integration/test_cli_run.py` |
| Validation helpers | non-string, empty string, whitespace-only values | `tests/unit/test_directives.py`, `tests/unit/test_graph_contracts.py`, `tests/unit/test_models_contracts.py` |
| Directive builders | invalid identifiers, duplicate option names, empty mappings/lists, invalid output paths, invalid analysis type, unsupported print format | `tests/unit/test_directives.py` |
| Graph topology | reserved node prefixes, unhashable nodes, duplicate grounds/devices, invalid branch/device containers, floating subgraphs, non-boolean run controls, invalid solver params | `tests/unit/test_graph.py`, `tests/unit/test_graph_contracts.py`, `tests/unit/test_simulate_contracts.py` |
| Compiler | deterministic node mapping, hidden-node expansion, repeated compile calls, defensive graph copies, malformed edge contracts, missing expanded graph guard | `tests/unit/test_compiler.py`, `tests/unit/test_compiler_contracts.py`, `tests/property/test_compiler_hypothesis.py` |
| Models and devices | invalid values, invalid model names, invalid terminal counts, raw template placeholder errors, invalid mapped nodes, abstract method guards, non-text measurement access | `tests/unit/test_models.py`, `tests/unit/test_models_contracts.py`, `tests/property/test_models_hypothesis.py` |
| Simulation helpers | unsupported directives, legacy signature handling, print-var validation, measurement node translation, inplace mutation safety, execution error propagation | `tests/unit/test_simulate_semantics.py`, `tests/unit/test_simulate_contracts.py`, `tests/integration/test_simulate_*.py` |
| Engine | subprocess success/failure, nested CSV output, cleanup behavior, target directory handling, Xyce error object fields | `tests/unit/test_engine.py`, `tests/unit/test_engine_contracts.py` |
| Output artifacts | missing required output, missing optional output, malformed CSV, text output parsing, path traversal rejection, read-only output maps | `tests/unit/test_outputs.py`, `tests/unit/test_netlists.py` |
| Raw netlist projects | missing `.END`, exact text preservation, from-file loading, run controls, cleanup after collection, missing output preservation | `tests/unit/test_netlists.py`, `tests/integration/test_raw_netlist_project.py` |
| Measurements | malformed lines, duplicate names, non-string input, numeric and non-numeric values, file reads | `tests/unit/test_measurements.py`, `tests/integration/test_measurements_real_xyce.py` |
| Parameter sweeps and Monte Carlo | duplicate parameters, existing `.PARAM` conflicts, invalid samples/seeds/distributions, invalid points, deterministic sampling, run aggregation | `tests/unit/test_sweeps.py`, `tests/integration/test_parameter_sweep_real_xyce.py` |
| XDM adapter | invalid args, missing/non-directory working dir, default working dir, nonzero exit, missing expected output, undeclared output text reads | `tests/unit/test_xdm.py` |
| Release and dependency policy | final/prerelease version gates, pip-audit allowlist validation, release smoke output | `tests/unit/test_release_helpers.py`, `tests/unit/test_pip_audit_policy.py`, `tools/release_smoke.py` |

Current local coverage gate: `PYTHONPATH=src .venv/bin/python -m pytest --cov=xyce_py --cov-report=term-missing -q` reports `100%` line coverage for `src/xyce_py`.
