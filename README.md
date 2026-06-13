# xyce-py

`xyce-py` is a small Python interface for building circuit topologies, compiling
them into Xyce-compatible netlists, running the Sandia Xyce simulator, and reading
simulation output back into Pandas.

The package does not replace Xyce. Xyce remains the simulation engine. `xyce-py`
handles the Python-side work around it: graph construction, SPICE netlist
generation, process execution, result loading, and node-name translation.

## What It Provides

- A `CircuitGraph` API for building circuits from named nodes, branches, and
  multi-terminal devices.
- Built-in models for common elements: resistors, capacitors, inductors, voltage
  sources, current sources, diodes, BJTs, MOSFETs, behavioral sources, and
  subcircuit instances.
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

## Supported Analysis Helpers

```python
result = graph.simulate_op()
result = graph.simulate_transient("1u", "20u")
result = graph.simulate_ac("DEC", "10", "1", "1e6")
result = graph.simulate_dc("V_supply", "0", "5", "0.5")
```

You can also call `graph.simulate(".OP")`, `graph.simulate(".TRAN ...")`,
`graph.simulate(".AC ...")`, or `graph.simulate(".DC ...")` directly.

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

## Models, Options, and Subcircuits

Raw Xyce directives can be attached to the graph when needed:

```python
graph.add_model(".MODEL DFAST D(IS=1e-9)")
graph.add_options(".OPTIONS DEVICE GMIN=1e-9")
graph.add_subcircuit(".SUBCKT BUF IN OUT\nR1 OUT IN 1k\n.ENDS")
```

Subcircuit definitions are passed through as opaque SPICE text. Xyce validates
subcircuit internals and arity during simulation.

## Parameters and Directive Builders

Use `add_parameter()` for `.PARAM` values in `CircuitGraph` netlists:

```python
graph.add_parameter("RLOAD", "1k")
graph.add_branch("vout", "gnd", [Resistor("load", "{RLOAD}")])
```

Directive builders emit exact SPICE directive text while leaving Xyce-specific
expressions to Xyce:

```python
from xyce_py import MeasureDirective, PrintDirective

print_line = PrintDirective("TRAN", ["V(out)"], file="tran.csv").to_spice()
measure_line = MeasureDirective(
    "TRAN",
    "rise_time",
    "TRIG V(out) VAL=0.1 RISE=1 TARG V(out) VAL=0.9 RISE=1",
).to_spice()
```

## Error Handling

`xyce-py` validates Python-side contracts early:

- Node identifiers must be hashable.
- Each graph may have only one ground node.
- Branches must contain at least one `CircuitElement`.
- Device terminal counts must match the device type.
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
