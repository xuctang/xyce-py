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
python -m pip install -e .
```

## Quick Start

```python
from xyce_py import CircuitGraph, Resistor, VoltageSource

graph = CircuitGraph()
graph.add_node("gnd", is_ground=True)
graph.add_branch("vin", "gnd", [VoltageSource("supply", 5.0)])
graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])

netlist = graph.simulate_op().netlist
print(netlist)
```

## Xyce Discovery

`xyce-py` looks for the Xyce executable in this order:

1. `/usr/local/XyceNF_7.10/bin/Xyce`
2. `Xyce` on your system `PATH`

You can also pass `xyce_path=` directly when constructing `CircuitGraph`.

## Testing

After installing the package into your virtual environment, run:

```bash
python -m unittest discover tests
```

If you want to run tests without installing the package, prepend `PYTHONPATH=src`.

## Packaging

Build the source distribution and wheel with:

```bash
python -m build
```

Validate the built metadata with:

```bash
python -m twine check dist/*
```
