# Graph input contract and solved graph projection

`xyce-py` is NetworkX-driven, but arbitrary NetworkX graph instances are not the
public simulation input. The supported topology input is `CircuitGraph`, whose
implementation owns an internal `networkx.MultiDiGraph`.

`MultiDiGraph` is required because the circuit topology needs parallel branches
between the same user nodes, directed terminal polarity, and compiler-expanded
internal nodes. Plain `Graph`, `DiGraph`, or `MultiGraph` inputs do not carry the
required circuit contracts by type alone.

If external NetworkX import is added later, it should be a strict
`CircuitGraph.from_networkx()` adapter. That adapter must define required node
and edge attributes, reject malformed graphs fail-fast, and avoid guessing
circuit meaning from arbitrary attributes.

For results, the canonical numeric output remains `SolveResult.waveforms`, a
Pandas `DataFrame`. Graph annotation is useful for topology inspection and
visualization, but it should not replace tabular waveform data for transient,
AC, DC, sweep, or current outputs.

`SolveResult.solved_graph(row=0)` returns a copy of the input circuit topology
with selected solved node voltages written as `solved_voltage` node attributes.
It does not mutate the original `CircuitGraph` or `SolveResult.original_graph`.
The method requires an explicit valid row index and rejects existing
`solved_voltage` attributes rather than overwriting user data.

Branch and device current annotation is intentionally not added here. The
compiler does not yet expose a one-to-one mapping from Xyce current output
columns to original graph edges/devices for every typed, raw-template, and
configurable feature path. Until that mapping exists, current data remains in
the waveform `DataFrame`.
