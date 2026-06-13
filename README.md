# xyce-py

`xyce-py` is a small Python interface for building circuit topologies, compiling
them into Xyce-compatible netlists, running the Sandia Xyce simulator, and reading
simulation output back into Pandas.

The package does not replace Xyce. Xyce remains the simulation engine. `xyce-py`
handles the Python-side work around it: graph construction, SPICE netlist
generation, process execution, result loading, and node-name translation.

For method-by-method documentation, see the
[API Reference](docs/api-reference.md).

## What It Provides

- A `CircuitGraph` API for building circuits from named nodes, branches, and
  multi-terminal devices.
- Built-in models for common elements: resistors, capacitors, inductors, voltage
  sources, current sources, diodes, BJTs, MOSFETs, behavioral sources, and
  subcircuit instances.
- Raw template devices for exact Xyce element lines that still need graph-owned
  node-name translation.
- A `NetlistCompiler` that converts the graph into a Xyce/SPICE-style netlist.
- Simulation helpers for operating point, transient, AC, and DC analyses.
- Typed directive builders for common outer contracts such as `.PARAM`,
  `.PRINT`, and `.MEASURE`.
- A raw `XyceProject` interface for exact netlists that use advanced Xyce
  syntax beyond the typed graph helpers.
- Pandas `DataFrame` output for waveforms, plus helpers to translate generated
  SPICE node names back to user node names.
- Fail-fast validation for invalid Python-side inputs and disconnected topologies
  before Xyce is launched.

## Requirements

- Python 3.10 or newer.
- Sandia Xyce installed separately and available either at
  `/usr/local/XyceNF_7.10/bin/Xyce` or on your `PATH` as `Xyce`.

Xyce is not bundled with this package. Install it from Sandia National
Laboratories before running simulations.

## Installation

From PyPI:

```bash
pip install xyce-py
```

For local development from this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[test]'
```

## Quick Start

This example builds a voltage divider and compiles it to a netlist. It does not
run Xyce.

```python
from xyce_py import CircuitGraph, NetlistCompiler, Resistor, VoltageSource

graph = CircuitGraph(xyce_path="Xyce")
graph.add_node("gnd", is_ground=True)
graph.add_branch("vin", "gnd", [VoltageSource("supply", 5.0)])
graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])

netlist = NetlistCompiler(graph.G, graph.spice_directives).compile()
print(netlist)
```

Generated netlist:

```spice
* Generated Circuit
.OPTIONS DEVICE GMIN=1e-8
V_supply N_1 0 DC 5.0
R_r1 N_1 N_2 1000.0
R_r2 N_2 0 1000.0
.END
```

## Run with Xyce

Use `CircuitGraph.simulate_op()` when Xyce is installed and available.

```python
from tempfile import TemporaryDirectory

from xyce_py import CircuitGraph, Resistor, VoltageSource, find_xyce_executable

with TemporaryDirectory() as tmpdir:
    graph = CircuitGraph(xyce_path=find_xyce_executable(), base_out_dir=tmpdir)
    graph.add_node("gnd", is_ground=True)
    graph.add_branch("vin", "gnd", [VoltageSource("supply", 5.0)])
    graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
    graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])

    result = graph.simulate_op()
    print(result.translated_waveforms())
```

`result.waveforms` contains Xyce's generated column names, such as `V(N_1)`.
`result.translated_waveforms()` returns a copy with voltage columns translated
back to the original user node names, such as `V(vin)` and `V(vout)`.

`result.solved_graph(row=0)` returns a copy of the input topology annotated with
solved node voltages for the selected waveform row:

```python
solved = result.solved_graph(row=0)
print(solved.nodes["vout"]["solved_voltage"])
```

The waveform `DataFrame` remains the canonical numeric result, especially for
time-series, frequency sweeps, and branch/device current columns. The solved
graph is an optional topology projection for node voltage inspection and
visualization.

Extra Xyce output files can be declared when the run directory is kept:

```python
from xyce_py import OutputSpec

graph.add_measurement("TRAN", "max_out", "MAX V(vout)")
result = graph.simulate_transient(
    "1n",
    "20n",
    output_specs=[OutputSpec.text("measurements", "circuit.cir.mt0")],
    keep_run_dir=True,
)
print(result.measurements()["MAX_OUT"].value)
```

## Input Graph Contract

The public topology input is `CircuitGraph`. A `CircuitGraph` owns an internal
`networkx.MultiDiGraph`, exposed as `graph.G` for inspection and low-level
compiler use.

`xyce-py` does not accept arbitrary external `nx.Graph`, `nx.DiGraph`, or
`nx.MultiGraph` instances as simulation input. Use `CircuitGraph.add_node()`,
`add_branch()`, and `add_device()` so topology data has the attributes required
by the compiler. `MultiDiGraph` is used because circuits need parallel branches,
directed terminal polarity, and compiler-expanded internal nodes.

If a future NetworkX import interface is added, it should be a strict
`CircuitGraph.from_networkx()` adapter with an explicit schema and fail-fast
validation. It should not guess circuit meaning from arbitrary graph attributes.

## Supported Analysis Helpers

```python
result = graph.simulate_op()
result = graph.simulate_transient("1u", "20u")
result = graph.simulate_ac("DEC", "10", "1", "1e6")
result = graph.simulate_dc("V_supply", "0", "5", "0.5")
```

You can also call `graph.simulate(".OP")`, `graph.simulate(".TRAN ...")`,
`graph.simulate(".AC ...")`, or `graph.simulate(".DC ...")` directly.

For advanced Xyce analyses, keep `simulate()` on its strict helper path and
compile the graph into a project with configurable Xyce feature specs:

```python
from xyce_py import XyceAnalysisSpec, XyceFeatureConfig, XyceOutputSpec

body = graph.compile_body()
vout = body.user_to_spice_node["vout"]
config = XyceFeatureConfig(
    analyses=[
        XyceAnalysisSpec(".NOISE", [f"V({vout})", "V_supply", "DEC", "10", "1", "1e6"]),
    ],
    outputs=[
        XyceOutputSpec("noise", "NOISE", ["ONOISE", "INOISE"], "noise.csv"),
    ],
)
project = graph.compile_project(
    "noise-analysis",
    config.directive_lines(),
    output_specs=config.output_specs(),
)
result = project.run(xyce_path="Xyce")
```

`compile_project()` validates topology, directive-list shape, output specs, and
package-owned `.END` insertion. It does not parse advanced Xyce semantics.
When configurable lines refer to graph nodes, use `compile_body()` to get the
generated SPICE node names.

See [Configurable Xyce Features](docs/configurable-features.md) for `.NOISE`,
`.HB`, `.SENS`, `.FOUR`, `.STEP`, arbitrary devices, arbitrary models, output
reports, XDM, and ADMS workflow examples.

## Run Raw Xyce Netlists

Use `XyceProject` when you already have an exact Xyce netlist, need an advanced
analysis directive, or want Xyce to remain the only parser for a feature.

```python
from xyce_py import OutputSpec, XyceProject

project = XyceProject(
    "raw-divider",
    """* raw voltage divider
V1 1 0 DC 10
R1 1 2 1000
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=raw.csv V(1) V(2)
.END
""",
    output_specs=(OutputSpec.csv("waveforms", "raw.csv"),),
)

result = project.run(xyce_path="Xyce")
print(result.outputs["waveforms"].frame)
```

For `.MEASURE` output, declare Xyce's generated measurement file as text and
parse it from the project result:

```python
from xyce_py import MeasureDirective, OutputSpec, XyceProject

project = XyceProject(
    "measured-run",
    f"""* measured transient
V1 in 0 PULSE(0 1 0 1n 1n 5n 10n)
R1 in out 1k
C1 out 0 1n
.TRAN 1n 20n
.PRINT TRAN FORMAT=CSV FILE=waveforms.csv V(out)
{MeasureDirective("TRAN", "max_out", "MAX V(out)").to_spice()}
.END
""",
    output_specs=(
        OutputSpec.csv("waveforms", "waveforms.csv"),
        OutputSpec.text("measurements", "circuit.cir.mt0"),
    ),
)

result = project.run(xyce_path="Xyce")
print(result.measurements()["MAX_OUT"].value)
```

The same raw-netlist path is available from the command line:

```bash
xyce-py run raw-divider.cir --csv-output waveforms raw.csv
```

The command prints a JSON summary containing the run directory, solve time, Xyce
stdout/stderr, and declared output metadata.

## Run Parameter Sweeps

Use `XyceParameterSweep` for Python-side sweeps over explicit `.PARAM` values:

```python
from xyce_py import OutputSpec, SweepParameter, XyceParameterSweep

sweep = XyceParameterSweep(
    "divider-sweep",
    """* sweep divider
V1 1 0 DC 10
R1 1 2 {RLOAD}
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=out.csv V(2)
.END
""",
    parameters=(SweepParameter("RLOAD", [1000, 3000]),),
    output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
)

result = sweep.run(xyce_path="Xyce")
print(result.run(0).point.parameters)
print(result.run(0).result.output("waveforms").frame)
```

Native Xyce `.STEP` netlists can still be run exactly through `XyceProject`.

For deterministic Monte Carlo sweeps, provide explicit distributions and a seed:

```python
from xyce_py import MonteCarloParameter, UniformDistribution, XyceMonteCarloSweep

monte_carlo = XyceMonteCarloSweep(
    "divider-monte-carlo",
    sweep.netlist_content,
    parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1000, 3000)),),
    samples=10,
    seed=7,
    output_specs=sweep.output_specs,
)
```

## Run XDM Translation

Use `XdmTranslator` to invoke an installed XDM translator with explicit XDM
arguments and validate the translated artifact:

```python
from xyce_py import XdmTranslator

translation = XdmTranslator(xdm_path="xdm").run(
    ["source.sp", "translated.cir"],
    working_dir=".",
    expected_output="translated.cir",
)

print(translation.translated_netlist_text())
```

## Models, Options, and Subcircuits

Raw Xyce directives can be attached to the graph when needed:

```python
graph.add_model(".MODEL DFAST D(IS=1e-9)")
graph.add_options(".OPTIONS DEVICE GMIN=1e-9")
graph.add_subcircuit(".SUBCKT BUF IN OUT\nR1 OUT IN 1k\n.ENDS")
```

Subcircuit definitions are passed through as opaque SPICE text. Xyce validates
subcircuit internals and arity during simulation.

Use raw template devices when Xyce already owns the exact element syntax but the
Python graph should still own topology and node-name translation:

```python
from xyce_py import RawNTerminalDevice, RawTwoTerminalElement

graph.add_branch(
    "vin",
    "vout",
    [RawTwoTerminalElement("load", "R_$name $node_pos $node_neg {RLOAD}")],
)
graph.add_device(
    RawNTerminalDevice(
        "amp",
        "AMP_MODEL",
        terminals=2,
        template="X_$name $n0 $n1 $model_name",
    ),
    ["vin", "vout"],
)
```

`RawTwoTerminalElement` requires `$node_pos` and `$node_neg`.
`RawNTerminalDevice` requires one ordered placeholder per terminal: `$n0`,
`$n1`, and so on. Both support `$name`; raw multi-terminal devices also support
`$model_name`.

## Parameters, Solver Options, and Directive Builders

Use `add_parameter()` for `.PARAM` values in `CircuitGraph` netlists:

```python
graph.add_parameter("RLOAD", "1k")
graph.add_branch("vout", "gnd", [Resistor("load", "{RLOAD}")])
```

Pass solver options as package-scoped `.OPTIONS` values:

```python
graph = CircuitGraph(
    xyce_path="Xyce",
    solver_params={"NONLIN": {"RELTOL": "1e-4"}},
)
```

Directive builders emit exact SPICE directive text while leaving Xyce-specific
expressions to Xyce:

```python
from xyce_py import MeasureDirective, OptionsDirective, PrintDirective

options_line = OptionsDirective("NONLIN", {"RELTOL": "1e-4"}).to_spice()
print_line = PrintDirective("TRAN", ["V(out)"], file="tran.csv").to_spice()
measure_line = MeasureDirective(
    "TRAN",
    "rise_time",
    "TRIG V(out) VAL=0.1 RISE=1 TARG V(out) VAL=0.9 RISE=1",
).to_spice()
```

Use configurable feature specs when the Xyce feature should be data-driven or is
outside the small typed helper set:

```python
from xyce_py import XyceDeviceSpec, XyceModelSpec

model_line = XyceModelSpec("DFAST", "D", {"IS": "1e-12"}).to_spice()
device_line = XyceDeviceSpec("D1", ["out", "0"], model_name="DFAST").to_spice()
```

## Error Handling

`xyce-py` validates Python-side contracts early:

- Node identifiers must be hashable.
- Each graph may have only one ground node.
- Branches must contain at least one `CircuitElement`.
- Device terminal counts must match the device type.
- `solver_params` must map Xyce option packages to option mappings.
- Floating subgraphs are rejected before launching Xyce.

If Xyce exits with a non-zero status, `xyce-py` raises `XyceRunError` with the
return code, stdout, stderr, run directory, netlist path, CSV path, and elapsed
solve time.

## Development and Testing

Install test dependencies:

```bash
python -m pip install -e '.[test]'
```

Run the full test suite:

```bash
pytest
```

Real-Xyce tests are marked with `@pytest.mark.xyce` and are skipped only when
Xyce is unavailable.

## Packaging

Build the source distribution and wheel:

```bash
python -m build
```

Validate the built metadata:

```bash
python -m twine check dist/*
```

See `docs/release.md` for the release checklist used before publishing.
See `docs/capability-matrix.md` for the supported and planned Xyce capability
surface.
