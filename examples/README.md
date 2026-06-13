# xyce-py Examples

These notebooks are designed as common user pipelines. They are intentionally
kept small and deterministic so users can inspect the flow before running Xyce.

| Notebook | Target audience | Pipeline |
| --- | --- | --- |
| `01_circuitgraph_quickstart.ipynb` | Python users building circuits programmatically | Build a `CircuitGraph`, compile a netlist, optionally run `.OP`, inspect waveforms and solved graph output |
| `02_raw_netlist_and_features.ipynb` | Existing Xyce users moving exact netlists into Python | Run raw Xyce projects and generate advanced directive projects with configurable feature specs |
| `03_sweeps_for_design_analysis.ipynb` | Design and data-analysis users exploring parameter spaces | Build deterministic parameter sweeps and Monte Carlo sweeps, inspect generated points and netlists |

The examples avoid hidden setup. Cells that require Xyce first check whether an
executable is available. Compile-only cells run with the Python package alone.
