# xyce-py Capability Matrix

This matrix tracks the public support surface against the current Xyce documentation areas listed by Sandia's Xyce Documentation & Tutorials page: Release Notes, Users' Guide, Reference Guide, XDM Users Guide, Building Guide, and Xyce/ADMS Users Guide.

## Support Levels

- **Supported**: has a public interface and automated tests.
- **Raw-supported**: available through exact raw netlist execution; Xyce remains the parser.
- **Config-supported**: available through configurable exact-text specs; Xyce remains the parser.
- **Partial**: available for common cases, with explicit limits.
- **Planned**: not exposed yet.

## Matrix

| Capability area | Current support | Public interface | Verification |
| --- | --- | --- | --- |
| Python circuit topology | Supported | `CircuitGraph` owning an internal `networkx.MultiDiGraph`, `NetlistCompiler`, `NetlistBody` | Unit, property, and real-Xyce integration tests |
| External NetworkX graph import | Planned | Future strict `CircuitGraph.from_networkx()` adapter only; arbitrary `nx.Graph`, `nx.DiGraph`, and `nx.MultiGraph` inputs are not accepted | ADR and documentation contract; implementation requires schema tests before support |
| Common two-terminal elements | Supported | `Resistor`, `Capacitor`, `Inductor`, `VoltageSource`, `CurrentSource`, `Diode`, `BehavioralSource` | Exact netlist unit tests and integration tests |
| Common multi-terminal devices | Supported | `BJT`, `MOSFET`, `Subcircuit` | Exact netlist and arity contract tests |
| Raw template graph devices | Raw-supported | `RawTwoTerminalElement`, `RawNTerminalDevice` | Exact-line unit tests, compiler tests, public export tests, release smoke, and real-Xyce integration test |
| Raw Xyce netlists | Supported | `XyceProject`, `CircuitGraph.compile_project` | Unit tests for exact execution contracts and output parsing; graph-compiled project unit and real-Xyce integration tests |
| Opaque Xyce directives | Config-supported | `add_model`, `add_options`, `add_subcircuit`, `RawDirective`, `XyceDirectiveSpec`, `XyceFeatureConfig`, raw project netlists | Directive contract tests, feature spec tests, graph-compiled project tests, and release smoke |
| Typed directive builders | Supported | `ParameterDirective`, `OptionsDirective`, `PrintDirective`, `MeasureDirective`, `RawDirective` | Exact-line unit tests and public export tests |
| Solver options | Supported | `CircuitGraph(..., solver_params={"PACKAGE": {"OPTION": value}})`, `OptionsDirective` | Unit tests for shape validation and ordering; real-Xyce integration test |
| Operating point analysis | Supported | `simulate_op`, `simulate(".OP")` | Unit and real-Xyce integration tests |
| Transient analysis | Supported | `simulate_transient`, `simulate(".TRAN ...")` | Unit and real-Xyce integration tests |
| AC analysis | Supported | `simulate_ac`, `simulate(".AC ...")` | Unit and real-Xyce integration tests |
| DC analysis | Supported | `simulate_dc`, `simulate(".DC ...")` | Unit and real-Xyce integration tests |
| Advanced analyses such as `.NOISE`, `.HB`, `.SENS`, `.FOUR`, `.STEP` | Config-supported | `XyceAnalysisSpec`, `XyceFeatureConfig`, `XyceProject` with exact netlist text, or `CircuitGraph.compile_project` with caller-owned directive lines | Exact-line feature tests, raw execution contract tests, graph-compiled project tests, and release smoke |
| Advanced device and model families | Config-supported | `XyceDeviceSpec`, `XyceModelSpec`, `RawTwoTerminalElement`, `RawNTerminalDevice`, raw project netlists | Exact-line feature tests, raw template tests, compiler tests, public export tests, release smoke, and real-Xyce integration test |
| Explicit output files and output modes | Supported | `OutputSpec`, `OutputArtifact`, `XyceOutputSpec`, `XyceReportSpec`, `XyceProjectResult.outputs`, `SolveResult.outputs`, graph `output_specs` | Unit tests for CSV, text, missing, optional, graph collection, malformed outputs, configurable `.PRINT`, and duplicate output names |
| Solved graph projection | Supported | `SolveResult.solved_graph(row=0)` returning a copied `networkx.MultiDiGraph` with node `solved_voltage` attributes | Unit tests for copy semantics, row selection, unmapped columns, ground skip, invalid row values, and existing attribute collision |
| Measurement extraction | Supported | `MeasureDirective`, `CircuitGraph.add_measurement`, `XyceProjectResult.measurements`, `SolveResult.measurements`, `parse_measurements`, `read_measurements` | Parser unit tests and real-Xyce `.mt0` integration tests |
| Parameterization, sweeps, and Monte Carlo | Supported | `CircuitGraph.add_parameter`, `ParameterDirective`, `SweepParameter`, `XyceParameterSweep`, `MonteCarloParameter`, `UniformDistribution`, `NormalDistribution`, `XyceMonteCarloSweep`, exact native sweep directives inside `XyceProject` netlists | Unit and real-Xyce `.PARAM`, Python-side sweep, and deterministic Monte Carlo tests |
| Schematic or XDM netlist import | Supported | `XdmTranslator`, `XdmTranslationResult`, `XdmTranslationError`, `XdmWorkflowSpec`, `XyceWorkflowSpec`, `XyceWorkflowResult`, `XyceWorkflowError` | Unit tests with fake external executables for success, failure, missing outputs, defaults, and command shape |
| Xyce/ADMS model development workflow | Config-supported | `AdmsWorkflowSpec`, `XyceWorkflowSpec`, `XyceWorkflowResult`, `XyceWorkflowError` | Unit tests for command shape, default executable, subprocess success/failure, and report collection |
| Command-line interface | Supported | `xyce-py run`, `python -m xyce_py run` | Unit tests for output declarations, JSON summary, and Xyce error propagation; package entry-point checks |

## Release Gate

Before a public release, every **Supported** and **Config-supported** row must
have unit tests, public API tests, documentation examples where appropriate, and
package-build validation. Every exact-text row must document that Xyce is the
parser and must preserve exact netlist text.
