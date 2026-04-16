# xyce-py

`xyce-py` is a NetworkX-driven Python wrapper for building circuit topologies, compiling Xyce netlists, and working with simulation results from the Sandia Xyce engine.

## Installation

**Note:** `xyce-py` requires the Sandia National Laboratories Xyce engine to be installed on your system. It is not bundled with this Python package. Download and install Xyce from Sandia's official site before using this tool.

Install the Python package from PyPI:

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

```python
from xyce_py import CircuitGraph, NetlistCompiler, Resistor, VoltageSource

graph = CircuitGraph(xyce_path="Xyce")
graph.add_node("gnd", is_ground=True)
graph.add_branch("vin", "gnd", [VoltageSource("supply", 5.0)])
graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])

netlist = NetlistCompiler(graph.G, graph.global_directives).compile()
print(netlist)
```

## Run with Xyce

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

## Xyce Discovery

`xyce-py` looks for the Xyce executable in this order:

1. `/usr/local/XyceNF_7.10/bin/Xyce`
2. `Xyce` on your system `PATH`

You can also pass `xyce_path=` directly when constructing `CircuitGraph`.

## Testing

After installing the package into your virtual environment, run:

```bash
python -m pip install -e '.[test]'
pytest
```

The suite is organized into `tests/unit`, `tests/integration`, `tests/property`, and
`tests/packaging`. Real-Xyce tests are marked with `@pytest.mark.xyce`.

## Packaging

Build the source distribution and wheel with:

```bash
python -m build
```

Validate the built metadata with:

```bash
python -m twine check dist/*
```

## Release Candidates

Release candidate builds use prerelease versions such as `1.0.1rc1` and publish to
TestPyPI first. Each release candidate must pass both the Linux and macOS self-hosted
Xyce release gates before a final release is cut.

Final releases use versions such as `1.0.1` and publish to PyPI only after a
successful TestPyPI rehearsal for the same release line, including the real-Xyce
Linux and macOS gates, registry-backed install smoke checks, and dependency audit.

See `docs/release.md` for the full release operator checklist.
