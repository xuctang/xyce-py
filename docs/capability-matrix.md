# xyce-py Capability Matrix

This matrix tracks the public support surface against the current Xyce documentation areas listed by Sandia's Xyce Documentation & Tutorials page: Release Notes, Users' Guide, Reference Guide, XDM Users Guide, Building Guide, and Xyce/ADMS Users Guide.

## Support Levels

- **Supported**: has a public interface and automated tests.
- **Raw-supported**: available through exact raw netlist execution; Xyce remains the parser.
- **Partial**: available for common cases, with explicit limits.
- **Planned**: not exposed yet.

## Matrix

| Capability area | Current support | Public interface | Verification |
| --- | --- | --- | --- |
| Python circuit topology | Supported | `CircuitGraph`, `NetlistCompiler` | Unit, property, and real-Xyce integration tests |
| Common two-terminal elements | Supported | `Resistor`, `Capacitor`, `Inductor`, `VoltageSource`, `CurrentSource`, `Diode`, `BehavioralSource` | Exact netlist unit tests and integration tests |
| Common multi-terminal devices | Supported | `BJT`, `MOSFET`, `Subcircuit` | Exact netlist and arity contract tests |
| Raw Xyce netlists | Supported | `XyceProject` | Unit tests for exact execution contracts and output parsing |
| Opaque Xyce directives | Partial | `add_model`, `add_options`, `add_subcircuit`, raw project netlists | Directive contract tests |
| Typed directive builders | Supported | `ParameterDirective`, `OptionsDirective`, `PrintDirective`, `MeasureDirective`, `RawDirective` | Exact-line unit tests and public export tests |
| Solver options | Supported | `CircuitGraph(..., solver_params={"PACKAGE": {"OPTION": value}})`, `OptionsDirective` | Unit tests for shape validation and ordering; real-Xyce integration test |
| Operating point analysis | Supported | `simulate_op`, `simulate(".OP")` | Unit and real-Xyce integration tests |
| Transient analysis | Supported | `simulate_transient`, `simulate(".TRAN ...")` | Unit and real-Xyce integration tests |
| AC analysis | Supported | `simulate_ac`, `simulate(".AC ...")` | Unit and real-Xyce integration tests |
| DC analysis | Supported | `simulate_dc`, `simulate(".DC ...")` | Unit and real-Xyce integration tests |
| Advanced analyses such as `.NOISE`, `.HB`, `.SENS`, `.FOUR`, `.STEP` | Raw-supported | `XyceProject` with exact netlist text | Raw execution contract tests; typed helpers planned |
| Explicit output files | Supported | `OutputSpec`, `OutputArtifact`, `XyceProjectResult.outputs` | Unit tests for CSV, text, missing, optional, and malformed outputs |
| Measurement extraction | Supported | `MeasureDirective`, `OutputSpec.text`, `XyceProjectResult.measurements`, `parse_measurements`, `read_measurements` | Parser unit tests and real-Xyce `.mt0` integration test |
| Parameterization and sweeps | Partial | `CircuitGraph.add_parameter`, `ParameterDirective`, exact sweep directives inside `XyceProject` netlists | Unit and real-Xyce `.PARAM` tests; sweep helpers planned |
| Schematic or XDM netlist import | Planned | None | XDM adapter planned |
| Xyce/ADMS model development workflow | Planned | None | External-tool adapter planned |
| Command-line interface | Supported | `xyce-py run`, `python -m xyce_py run` | Unit tests for output declarations, JSON summary, and Xyce error propagation; package entry-point checks |

## Release Gate

Before a public release, every **Supported** row must have unit tests, public API tests, documentation examples where appropriate, and package-build validation. Every **Raw-supported** row must document that Xyce is the parser and must preserve exact netlist text.
