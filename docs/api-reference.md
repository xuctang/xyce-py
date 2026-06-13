# xyce-py API Reference

This reference documents the public Python surface exported from `xyce_py`.
Names starting with `_` are private implementation details and are not supported
as user-facing interfaces.

The primary topology input is `CircuitGraph`. It owns an internal
`networkx.MultiDiGraph`; arbitrary external NetworkX graphs are not accepted as
simulation inputs unless a future strict adapter is added.

## Circuit Topology

### `CircuitGraph`

`CircuitGraph(xyce_path=None, base_out_dir="_xyce_runs", solver_params=None)`

Builds, validates, compiles, and simulates a circuit topology.

Parameters:
- `xyce_path`: path to the Xyce executable. If `None`, `find_xyce_executable()` is used.
- `base_out_dir`: directory for generated Xyce run directories.
- `solver_params`: optional mapping of Xyce `.OPTIONS` package names to option mappings.

Attributes:
- `G`: internal `networkx.MultiDiGraph` topology.
- `xyce_path`: resolved executable path.
- `base_out_dir`: resolved output base directory.
- `solver_params`: normalized solver option mapping.
- `spice_directives`: emitted SPICE directive lines.
- `measurement_directives`: stored `.MEASURE` directives.

Methods:
- `CircuitGraph.add_node(node_id, is_ground=False)`: adds a hashable user node. Set `is_ground=True` for the single ground reference.
- `CircuitGraph.add_branch(node_a, node_b, elements)`: adds a branch containing a non-empty `list[CircuitElement]`.
- `CircuitGraph.add_device(device, nodes)`: adds an `NTerminalDevice` with ordered terminal node ids.
- `CircuitGraph.add_model(model_string)`: appends a raw `.MODEL` directive string.
- `CircuitGraph.add_options(options_string)`: appends a raw `.OPTIONS` directive string.
- `CircuitGraph.add_parameter(name, value)`: appends a `.PARAM` directive from a validated name and value.
- `CircuitGraph.add_measurement(analysis_type, name, expression)`: stores a `.MEASURE` directive for later emission.
- `CircuitGraph.add_subcircuit(subckt_string)`: appends an opaque `.SUBCKT ... .ENDS` block.
- `CircuitGraph.compile_body()`: returns `NetlistBody` without analysis directives or `.END`.
- `CircuitGraph.compile_project(name, simulation_directives, output_specs=())`: returns an `XyceProject` by appending directive strings or `to_spice()` specs and a package-owned `.END`.
- `CircuitGraph.simulate(analysis_cmd, *, print_vars=None, inplace=False, output_specs=None, keep_run_dir=False)`: runs `.OP`, `.TRAN`, `.AC`, or `.DC` and returns `SolveResult`.
- `CircuitGraph.simulate_op(print_vars=None, inplace=False, output_specs=None, keep_run_dir=False)`: convenience wrapper for `.OP`.
- `CircuitGraph.simulate_transient(step, stop, start="0", print_vars=None, inplace=False, output_specs=None, keep_run_dir=False)`: convenience wrapper for `.TRAN`.
- `CircuitGraph.simulate_ac(sweep_type, points, start_freq, stop_freq, print_vars=None, output_specs=None, keep_run_dir=False)`: convenience wrapper for `.AC`.
- `CircuitGraph.simulate_dc(source_name, start, stop, step, print_vars=None, output_specs=None, keep_run_dir=False)`: convenience wrapper for `.DC`.

Important behavior:
- Exactly one ground node is required before compilation.
- Floating subgraphs are rejected before Xyce is launched.
- `simulate()` intentionally rejects unsupported analysis directives. Use `compile_project()` or `XyceProject` for advanced Xyce syntax.
- `inplace=True` is a narrow single-row convenience that mutates `CircuitGraph.G` with `solved_voltage`; prefer `SolveResult.solved_graph()`.

Raises:
- `CircuitTopologyError` for missing ground, multiple grounds, or floating topology.
- `TypeError` / `ValueError` for invalid Python-side inputs.
- `XyceRunError` when Xyce exits non-zero.

### `CircuitTopologyError`

Raised when topology validation fails before Xyce is launched.

### `NetlistCompiler`

`NetlistCompiler(graph, spice_directives)`

Compiles a `networkx.MultiDiGraph` topology and directive list into Xyce netlist text.

Parameters:
- `graph`: a `networkx.MultiDiGraph` using `CircuitGraph` topology attributes.
- `spice_directives`: list of directive strings emitted before element/device lines.

Properties:
- `NetlistCompiler.user_to_spice_node`: read-only mapping from user node ids to generated SPICE node ids.
- `NetlistCompiler.spice_to_user_node`: read-only reverse mapping.
- `NetlistCompiler.expanded_graph`: copy of the compiler-expanded graph, or `None` before compilation.

Methods:
- `NetlistCompiler.compile()`: returns complete netlist text ending with `.END`.
- `NetlistCompiler.compile_body()`: returns `NetlistBody` without `.END`.

### `NetlistBody`

`NetlistBody(lines, user_to_spice_node, spice_to_user_node, expanded_graph)`

Compiler output before analysis directives and `.END`.

Fields:
- `lines`: netlist body lines.
- `user_to_spice_node`: mapping from user node ids to generated SPICE node ids.
- `spice_to_user_node`: reverse mapping.
- `expanded_graph`: copied `networkx.MultiDiGraph` after series expansion.

## Circuit Elements and Devices

### `CircuitElement`

`CircuitElement(name)`

Abstract base for two-terminal elements.

Parameters:
- `name`: non-empty element name.

Methods:
- `CircuitElement.to_spice(node_pos, node_neg)`: abstract method returning an exact element line.

### `NTerminalDevice`

`NTerminalDevice(name, model_name)`

Abstract base for multi-terminal devices.

Parameters:
- `name`: non-empty device name.
- `model_name`: non-empty Xyce model or subcircuit name.

Properties:
- `NTerminalDevice.expected_terminals`: required terminal count.

Methods:
- `NTerminalDevice.to_spice(mapped_nodes)`: abstract method returning an exact device line.

### `Resistor`

`Resistor(name, value)`

Two-terminal resistor.

Parameters:
- `name`: non-empty element name.
- `value`: numeric value or non-empty Xyce expression string.

Methods:
- `Resistor.to_spice(node_pos, node_neg)`: emits `R_<name> node_pos node_neg value`.

### `Capacitor`

`Capacitor(name, value)`

Two-terminal capacitor.

Parameters:
- `name`: non-empty element name.
- `value`: numeric value or non-empty Xyce expression string.

Methods:
- `Capacitor.to_spice(node_pos, node_neg)`: emits `C_<name> node_pos node_neg value`.

### `Inductor`

`Inductor(name, value)`

Two-terminal inductor.

Parameters:
- `name`: non-empty element name.
- `value`: numeric value or non-empty Xyce expression string.

Methods:
- `Inductor.to_spice(node_pos, node_neg)`: emits `L_<name> node_pos node_neg value`.

### `VoltageSource`

`VoltageSource(name, dc_value, transient_expr=None)`

Two-terminal voltage source.

Parameters:
- `name`: non-empty element name.
- `dc_value`: numeric DC value.
- `transient_expr`: optional non-empty Xyce transient expression.

Methods:
- `VoltageSource.to_spice(node_pos, node_neg)`: emits a `V_<name>` source line.

### `CurrentSource`

`CurrentSource(name, dc_value, transient_expr=None)`

Two-terminal current source.

Parameters:
- `name`: non-empty element name.
- `dc_value`: numeric DC value.
- `transient_expr`: optional non-empty Xyce transient expression.

Methods:
- `CurrentSource.to_spice(node_pos, node_neg)`: emits an `I_<name>` source line.

### `Diode`

`Diode(name, model_name)`

Two-terminal diode.

Parameters:
- `name`: non-empty element name.
- `model_name`: non-empty model name.

Methods:
- `Diode.to_spice(node_pos, node_neg)`: emits `D_<name> node_pos node_neg model_name`.

### `BJT`

`BJT(name, model_name)`

Three-terminal bipolar transistor.

Parameters:
- `name`: non-empty device name.
- `model_name`: non-empty model name.

Properties:
- `BJT.expected_terminals`: always `3`.

Methods:
- `BJT.to_spice(mapped_nodes)`: emits `Q_<name> collector base emitter model_name`.

### `MOSFET`

`MOSFET(name, model_name)`

Four-terminal MOSFET.

Parameters:
- `name`: non-empty device name.
- `model_name`: non-empty model name.

Properties:
- `MOSFET.expected_terminals`: always `4`.

Methods:
- `MOSFET.to_spice(mapped_nodes)`: emits `M_<name> drain gate source bulk model_name`.

### `Subcircuit`

`Subcircuit(name, model_name, terminals)`

Arbitrary subcircuit instance with caller-declared terminal count.

Parameters:
- `name`: non-empty instance name.
- `model_name`: non-empty `.SUBCKT` name.
- `terminals`: positive integer terminal count.

Properties:
- `Subcircuit.expected_terminals`: equals `terminals`.

Methods:
- `Subcircuit.to_spice(mapped_nodes)`: emits `X_<name> ... model_name`.

### `BehavioralSource`

`BehavioralSource(name, equation, source_type)`

Two-terminal behavioral source.

Parameters:
- `name`: non-empty source name.
- `equation`: non-empty Xyce expression.
- `source_type`: non-empty source type token such as `V` or `I`.

Methods:
- `BehavioralSource.to_spice(node_pos, node_neg)`: emits `B_<name> node_pos node_neg source_type={equation}`.

### `RawTwoTerminalElement`

`RawTwoTerminalElement(name, template)`

Two-terminal raw template element for exact Xyce element lines.

Parameters:
- `name`: non-empty element name.
- `template`: `string.Template` text containing `$name`, `$node_pos`, and `$node_neg`.

Methods:
- `RawTwoTerminalElement.to_spice(node_pos, node_neg)`: substitutes the template.

### `RawNTerminalDevice`

`RawNTerminalDevice(name, model_name, terminals, template)`

N-terminal raw template device for exact Xyce device lines.

Parameters:
- `name`: non-empty device name.
- `model_name`: non-empty model name.
- `terminals`: positive integer terminal count.
- `template`: `string.Template` text containing `$n0` through `$n{terminals-1}`. It may also use `$name` and `$model_name`.

Properties:
- `RawNTerminalDevice.expected_terminals`: equals `terminals`.

Methods:
- `RawNTerminalDevice.to_spice(mapped_nodes)`: substitutes mapped terminal nodes into the template.

## Simulation Results

### `SolveResult`

`SolveResult(original_graph, expanded_graph, netlist, waveforms, solve_time_sec, stdout, spice_to_user_node, outputs={})`

Returned from `CircuitGraph.simulate*()`.

Fields:
- `original_graph`: copy of the pre-compile `networkx.MultiDiGraph`.
- `expanded_graph`: copy of the compiler-expanded graph.
- `netlist`: exact netlist text sent to Xyce.
- `waveforms`: Pandas `DataFrame` read from Xyce CSV output.
- `solve_time_sec`: elapsed Xyce subprocess time.
- `stdout`: Xyce stdout.
- `spice_to_user_node`: generated SPICE node id to user node id mapping.
- `outputs`: read-only mapping from output name to `OutputArtifact`.

Methods:
- `SolveResult.translated_waveforms()`: returns a copied `DataFrame` with `V(N_*)` columns translated to user node names when possible.
- `SolveResult.solved_graph(row=0)`: returns a copied `networkx.MultiDiGraph` annotated with node `solved_voltage` values from the selected waveform row.
- `SolveResult.output(name)`: returns one named `OutputArtifact`.
- `SolveResult.measurements(output_name="measurements")`: parses a text output artifact as Xyce `.MEASURE` results.

Raises:
- `TypeError` if `solved_graph(row=...)` row is not an integer.
- `IndexError` if `row` is outside `waveforms`.
- `RuntimeError` if a target node already has `solved_voltage`.
- `TypeError` if `measurements()` targets a non-text artifact.

## Raw Netlist Projects

### `XyceProject`

`XyceProject(name, netlist_content, output_specs=())`

Exact raw Xyce netlist plus declared output artifacts.

Parameters:
- `name`: non-empty project name.
- `netlist_content`: exact netlist text containing a top-level `.END`.
- `output_specs`: tuple or iterable of `OutputSpec` declarations.

Methods:
- `XyceProject.from_file(path, *, output_specs=(), name=None)`: reads netlist text from a file and returns a project.
- `XyceProject.run(*, xyce_path=None, base_out_dir="_xyce_runs", run_name=None, target_dir=None, keep_run_dir=True)`: runs Xyce and returns `XyceProjectResult`.

### `XyceProjectResult`

`XyceProjectResult(execution, outputs)`

Returned from `XyceProject.run()`.

Fields:
- `execution`: `XyceExecutionResult`.
- `outputs`: read-only mapping from output name to `OutputArtifact`.

Properties:
- `XyceProjectResult.run_dir`: run directory path.
- `XyceProjectResult.stdout`: Xyce stdout.
- `XyceProjectResult.stderr`: Xyce stderr.
- `XyceProjectResult.solve_time_sec`: elapsed solve time.

Methods:
- `XyceProjectResult.output(name)`: returns one named `OutputArtifact`.
- `XyceProjectResult.measurements(output_name="measurements")`: parses a text output artifact as Xyce `.MEASURE` results.

## Outputs

### `OutputSpec`

`OutputSpec(name, path, kind="csv", required=True)`

Declares an output file expected inside the Xyce run directory.

Parameters:
- `name`: unique non-empty output name.
- `path`: relative file path inside the Xyce run directory.
- `kind`: exactly `"csv"` or `"text"`.
- `required`: boolean. Missing required outputs raise `FileNotFoundError`.

Methods:
- `OutputSpec.csv(name, path, *, required=True)`: convenience constructor for CSV output.
- `OutputSpec.text(name, path, *, required=True)`: convenience constructor for text output.
- `OutputSpec.resolve_path(run_dir)`: resolves the relative path under `run_dir`.

### `OutputArtifact`

`OutputArtifact(spec, path, exists, frame=None, text=None)`

Loaded output file metadata and parsed content.

Fields:
- `spec`: source `OutputSpec`.
- `path`: resolved filesystem path.
- `exists`: whether the output file existed at collection time.
- `frame`: Pandas `DataFrame` for CSV outputs.
- `text`: string content for text outputs.

## Directive Builders

### `RawDirective`

`RawDirective(text)`

Opaque SPICE directive line.

Parameters:
- `text`: non-empty directive text starting with `.`.

Methods:
- `RawDirective.to_spice()`: returns the normalized directive text.

### `ParameterDirective`

`ParameterDirective(name, value)`

Typed `.PARAM` directive.

Parameters:
- `name`: SPICE identifier.
- `value`: non-empty string or numeric value.

Methods:
- `ParameterDirective.to_spice()`: emits `.PARAM name=value`.

### `OptionsDirective`

`OptionsDirective(package, values)`

Typed `.OPTIONS` directive.

Parameters:
- `package`: SPICE identifier for the option package.
- `values`: non-empty mapping of option names to string or numeric values.

Methods:
- `OptionsDirective.to_spice()`: emits `.OPTIONS package key=value ...`.

### `PrintDirective`

`PrintDirective(analysis_type, variables, *, file="output.csv", output_format="CSV")`

Typed `.PRINT` directive for CSV output.

Parameters:
- `analysis_type`: analysis name without leading `.`.
- `variables`: non-empty list of variable strings.
- `file`: relative output CSV path.
- `output_format`: must be `"CSV"`.

Methods:
- `PrintDirective.to_spice()`: emits `.PRINT analysis FORMAT=CSV FILE=file variables...`.

### `MeasureDirective`

`MeasureDirective(analysis_type, name, expression)`

Typed `.MEASURE` directive.

Parameters:
- `analysis_type`: analysis name without leading `.`.
- `name`: SPICE identifier.
- `expression`: non-empty measurement expression.

Methods:
- `MeasureDirective.to_spice()`: emits `.MEASURE analysis name expression`.

## Configurable Xyce Feature Specs

### `XyceDirectiveSpec`

`XyceDirectiveSpec(directive, positional=(), parameters=None, expression=None)`

Configurable exact directive line.

Parameters:
- `directive`: directive token starting with `.`, excluding `.END`.
- `positional`: list or tuple of positional string items.
- `parameters`: optional mapping emitted as `key=value`.
- `expression`: optional raw trailing expression string.

Methods:
- `XyceDirectiveSpec.from_mapping(mapping)`: constructs from a mapping and rejects unknown keys.
- `XyceDirectiveSpec.to_spice()`: emits the exact directive line.

### `XyceAnalysisSpec`

`XyceAnalysisSpec(directive, positional=(), parameters=None, expression=None)`

Analysis-specific alias of `XyceDirectiveSpec`.

Parameters:
- same as `XyceDirectiveSpec`.

Methods:
- `XyceAnalysisSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceAnalysisSpec.to_spice()`: emits the exact analysis line.

### `XyceModelSpec`

`XyceModelSpec(model_name, model_type, parameters=None)`

Configurable `.MODEL` line.

Parameters:
- `model_name`: single non-empty netlist token.
- `model_type`: single non-empty model type token.
- `parameters`: optional mapping emitted inside parentheses.

Methods:
- `XyceModelSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceModelSpec.to_spice()`: emits `.MODEL model_name model_type(...)`.

### `XyceDeviceSpec`

`XyceDeviceSpec(device_name, nodes, model_name=None, parameters=None, expression=None)`

Configurable exact device or element instance line.

Parameters:
- `device_name`: exact Xyce instance token.
- `nodes`: non-empty list or tuple of node tokens.
- `model_name`: optional model token.
- `parameters`: optional mapping emitted as `key=value`.
- `expression`: optional raw trailing expression.

Methods:
- `XyceDeviceSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceDeviceSpec.to_spice()`: emits the exact instance line.

### `XyceOutputSpec`

`XyceOutputSpec(name, analysis_type, variables, file, output_format="CSV", kind="csv", required=True, directive=".PRINT")`

Configurable output directive plus output artifact declaration.

Parameters:
- `name`: output artifact name.
- `analysis_type`: analysis type without leading `.`.
- `variables`: non-empty list or tuple of Xyce output variable strings.
- `file`: relative output file path.
- `output_format`: output format token, usually `"CSV"`.
- `kind`: artifact parser kind, `"csv"` or `"text"`.
- `required`: boolean.
- `directive`: directive token, default `.PRINT`.

Methods:
- `XyceOutputSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceOutputSpec.to_spice()`: emits the output directive line.
- `XyceOutputSpec.output_spec()`: returns the matching `OutputSpec`.

### `XyceReportSpec`

`XyceReportSpec(name, path, kind="text", required=True)`

Declares a report artifact without emitting a netlist directive.

Parameters:
- `name`: output artifact name.
- `path`: relative report path.
- `kind`: `"csv"` or `"text"`.
- `required`: boolean.

Methods:
- `XyceReportSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceReportSpec.output_spec()`: returns the matching `OutputSpec`.

### `XyceFeatureConfig`

`XyceFeatureConfig(directives=(), models=(), devices=(), analyses=(), outputs=(), reports=(), workflows=())`

Groups configurable feature specs.

Parameters:
- `directives`: `XyceDirectiveSpec` instances or mappings.
- `models`: `XyceModelSpec` instances or mappings.
- `devices`: `XyceDeviceSpec` instances or mappings.
- `analyses`: `XyceAnalysisSpec` instances or mappings.
- `outputs`: `XyceOutputSpec` instances or mappings.
- `reports`: `XyceReportSpec` instances or mappings.
- `workflows`: `XyceWorkflowSpec` instances or mappings.

Methods:
- `XyceFeatureConfig.from_mapping(mapping)`: constructs a config and rejects unknown top-level keys.
- `XyceFeatureConfig.directive_lines()`: returns emitted netlist lines for directives, models, devices, analyses, and outputs.
- `XyceFeatureConfig.output_specs()`: returns output specs from outputs and reports.

## External Workflows

### `XyceWorkflowSpec`

`XyceWorkflowSpec(executable, arguments=(), working_dir=None, expected_outputs=())`

Generic external workflow command.

Parameters:
- `executable`: non-empty executable path or name.
- `arguments`: list or tuple of non-empty argument strings.
- `working_dir`: existing directory, or `None` for current directory.
- `expected_outputs`: report specs to collect after success.

Methods:
- `XyceWorkflowSpec.from_mapping(mapping)`: constructs from a mapping.
- `XyceWorkflowSpec.to_command()`: returns `(executable, *arguments)`.
- `XyceWorkflowSpec.run()`: runs the command without a shell and returns `XyceWorkflowResult`.

Raises:
- `XyceWorkflowError` on non-zero exit.
- `FileNotFoundError` for missing required outputs or working directory.
- `NotADirectoryError` for invalid working directory.

### `XdmWorkflowSpec`

`XdmWorkflowSpec(executable="xdm", arguments=(), working_dir=None, expected_outputs=())`

XDM-flavored workflow spec.

Parameters:
- same as `XyceWorkflowSpec`, with default executable `"xdm"`.

Methods:
- `XdmWorkflowSpec.from_mapping(mapping)`: constructs from a mapping.
- `XdmWorkflowSpec.to_command()`: inherited command tuple builder.
- `XdmWorkflowSpec.run()`: inherited workflow runner.

### `AdmsWorkflowSpec`

`AdmsWorkflowSpec(executable="admsXml", arguments=(), working_dir=None, expected_outputs=())`

ADMS-flavored workflow spec.

Parameters:
- same as `XyceWorkflowSpec`, with default executable `"admsXml"`.

Methods:
- `AdmsWorkflowSpec.from_mapping(mapping)`: constructs from a mapping.
- `AdmsWorkflowSpec.to_command()`: inherited command tuple builder.
- `AdmsWorkflowSpec.run()`: inherited workflow runner.

### `XyceWorkflowResult`

`XyceWorkflowResult(command, working_dir, stdout, stderr, elapsed_sec, outputs={})`

Result of a successful `XyceWorkflowSpec.run()`.

Fields:
- `command`: command tuple.
- `working_dir`: resolved working directory.
- `stdout`: captured stdout.
- `stderr`: captured stderr.
- `elapsed_sec`: elapsed subprocess time.
- `outputs`: read-only mapping of collected output artifacts.

### `XyceWorkflowError`

Raised when `XyceWorkflowSpec.run()` exits non-zero.

Attributes:
- `command`
- `returncode`
- `stdout`
- `stderr`
- `working_dir`
- `elapsed_sec`

### `XdmTranslator`

`XdmTranslator(xdm_path="xdm")`

Adapter for installed XDM translators.

Parameters:
- `xdm_path`: executable path or command name.

Methods:
- `XdmTranslator.run(arguments, *, working_dir=None, expected_output=None)`: invokes XDM and returns `XdmTranslationResult`.

### `XdmTranslationResult`

`XdmTranslationResult(command, working_dir, stdout, stderr, elapsed_sec, output_path=None)`

Result of a successful XDM translation.

Fields:
- `command`: command tuple.
- `working_dir`: resolved working directory.
- `stdout`: captured stdout.
- `stderr`: captured stderr.
- `elapsed_sec`: elapsed subprocess time.
- `output_path`: optional translated output path.

Methods:
- `XdmTranslationResult.translated_netlist_text()`: reads `output_path` text.

### `XdmTranslationError`

Raised when `XdmTranslator.run()` exits non-zero.

Attributes:
- `command`
- `returncode`
- `stdout`
- `stderr`
- `working_dir`
- `elapsed_sec`

## Sweeps

### `SweepParameter`

`SweepParameter(name, values)`

One explicit Python-side sweep parameter.

Parameters:
- `name`: SPICE identifier.
- `values`: non-empty list of string or numeric values. Lists are required.

### `SweepPoint`

`SweepPoint(index, parameters)`

One concrete sweep point.

Parameters:
- `index`: non-negative integer.
- `parameters`: non-empty mapping of parameter names to normalized string values.

### `SweepRunResult`

`SweepRunResult(point, result)`

One completed sweep run.

Fields:
- `point`: `SweepPoint`.
- `result`: `XyceProjectResult`.

### `XyceParameterSweep`

`XyceParameterSweep(name, netlist_content, parameters, output_specs=())`

Runs explicit Cartesian-product parameter sweeps by inserting `.PARAM` lines.

Parameters:
- `name`: non-empty sweep name.
- `netlist_content`: raw netlist text containing `.END`.
- `parameters`: non-empty tuple of `SweepParameter` instances.
- `output_specs`: output declarations shared by every point.

Methods:
- `XyceParameterSweep.from_file(path, *, parameters, output_specs=(), name=None)`: loads sweep netlist text from a file.
- `XyceParameterSweep.points()`: returns all `SweepPoint` combinations.
- `XyceParameterSweep.netlist_for_point(point)`: returns netlist text for one point.
- `XyceParameterSweep.run(*, xyce_path=None, base_out_dir="_xyce_runs", run_name=None, keep_run_dirs=True)`: runs every point and returns `XyceParameterSweepResult`.

### `XyceParameterSweepResult`

`XyceParameterSweepResult(name, runs)`

Completed parameter or Monte Carlo sweep.

Parameters:
- `name`: non-empty sweep name.
- `runs`: non-empty tuple of `SweepRunResult`.

Methods:
- `XyceParameterSweepResult.run(index)`: returns the run with matching point index.

### `UniformDistribution`

`UniformDistribution(low, high)`

Uniform random distribution for Monte Carlo sweeps.

Parameters:
- `low`: numeric lower bound.
- `high`: numeric upper bound greater than `low`.

Methods:
- `UniformDistribution.sample(rng)`: samples with the supplied `random.Random`.

### `NormalDistribution`

`NormalDistribution(mean, stddev)`

Normal random distribution for Monte Carlo sweeps.

Parameters:
- `mean`: numeric mean.
- `stddev`: positive numeric standard deviation.

Methods:
- `NormalDistribution.sample(rng)`: samples with the supplied `random.Random`.

### `MonteCarloParameter`

`MonteCarloParameter(name, distribution)`

One Monte Carlo parameter.

Parameters:
- `name`: SPICE identifier.
- `distribution`: `UniformDistribution` or `NormalDistribution`.

### `XyceMonteCarloSweep`

`XyceMonteCarloSweep(name, netlist_content, parameters, samples, seed=0, output_specs=())`

Runs deterministic sampled parameter sweeps.

Parameters:
- `name`: non-empty sweep name.
- `netlist_content`: raw netlist text containing `.END`.
- `parameters`: non-empty tuple of `MonteCarloParameter`.
- `samples`: positive integer sample count.
- `seed`: integer random seed.
- `output_specs`: output declarations shared by every point.

Methods:
- `XyceMonteCarloSweep.points()`: returns deterministic sampled `SweepPoint` values.
- `XyceMonteCarloSweep.netlist_for_point(point)`: returns netlist text for one sampled point.
- `XyceMonteCarloSweep.run(*, xyce_path=None, base_out_dir="_xyce_runs", run_name=None, keep_run_dirs=True)`: runs every sampled point and returns `XyceParameterSweepResult`.

## Measurements

### `MeasurementResult`

`MeasurementResult(name, value_text, value)`

Parsed `.MEASURE` result.

Fields:
- `name`: measurement name.
- `value_text`: original value string.
- `value`: parsed float, or `None` if the value is non-numeric.

### `parse_measurements`

`parse_measurements(measurement_text)`

Parses Xyce measurement text.

Parameters:
- `measurement_text`: string containing `NAME = value` lines.

Returns:
- read-only mapping from upper-case measurement names to `MeasurementResult`.

### `read_measurements`

`read_measurements(path)`

Reads a measurement file and calls `parse_measurements()`.

Parameters:
- `path`: string or `Path` to a measurement text file.

Returns:
- read-only mapping from upper-case measurement names to `MeasurementResult`.

## Low-level Execution

### `find_xyce_executable`

`find_xyce_executable()`

Returns the preferred Xyce executable path. It checks `/usr/local/XyceNF_7.10/bin/Xyce`, then `PATH`, then returns `"Xyce"`.

### `run_xyce_netlist`

`run_xyce_netlist(*, xyce_path, base_out_dir, netlist_content, csv_name, run_name="run", target_dir=None, keep_run_dir=False)`

Low-level execution helper used by graph and project runs.

Parameters:
- `xyce_path`: executable path or command name.
- `base_out_dir`: base run directory when `target_dir` is not supplied.
- `netlist_content`: exact netlist text to write to `circuit.cir`.
- `csv_name`: CSV path to read after a successful Xyce run.
- `run_name`: run directory name under `base_out_dir`.
- `target_dir`: exact run directory override.
- `keep_run_dir`: if `False`, removes the generated netlist, CSV, and `.prn` file after reading.

Returns:
- `XyceExecutionResult`.

Raises:
- `XyceRunError` when Xyce exits non-zero.

### `XyceExecutionResult`

`XyceExecutionResult(run_dir, netlist_path, stdout, stderr, waveforms, solve_time_sec)`

Low-level execution result.

Fields:
- `run_dir`: run directory path.
- `netlist_path`: written netlist path.
- `stdout`: Xyce stdout.
- `stderr`: Xyce stderr.
- `waveforms`: Pandas `DataFrame` loaded from `csv_name`.
- `solve_time_sec`: elapsed subprocess time.

### `XyceRunError`

Raised when Xyce exits non-zero.

Attributes:
- `returncode`
- `stdout`
- `stderr`
- `run_dir`
- `netlist_path`
- `csv_path`
- `solve_time_sec`

## Command Line

The console entry point is:

```bash
xyce-py run NETLIST
```

Equivalent module invocation:

```bash
python -m xyce_py run NETLIST
```

Options:
- `--name NAME`: project name.
- `--xyce-path PATH`: Xyce executable path.
- `--base-out-dir DIR`: base output directory.
- `--run-name NAME`: run directory name.
- `--target-dir DIR`: exact run directory.
- `--discard-run-dir`: remove declared artifacts after parsing.
- `--csv-output NAME PATH`: declare a required CSV output.
- `--text-output NAME PATH`: declare a required text output.
- `--optional-csv-output NAME PATH`: declare an optional CSV output.
- `--optional-text-output NAME PATH`: declare an optional text output.
