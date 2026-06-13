# Graph-compiled Xyce projects

`CircuitGraph.compile_body()` exposes the compiler result and generated node mappings for callers that need to build advanced Xyce directives explicitly. `CircuitGraph.compile_project()` appends caller-owned directive lines to that compiled body and returns an `XyceProject`.

This is the supported graph-level path for Xyce analyses that are not represented by `simulate_op()`, `simulate_transient()`, `simulate_ac()`, `simulate_dc()`, or `simulate()`. The package validates topology, directive-list shape, output specs, and `.END` ownership. It does not infer `.PRINT` semantics or parse directives such as `.NOISE`, `.HB`, `.SENS`, `.FOUR`, `.MEASURE`, or `.STEP`; Xyce remains the authority for those directives.

The boundary keeps `simulate()` strict because it owns waveform CSV generation and print-type inference for the four typed helpers. Advanced analyses use the raw project execution path, where callers declare exact output files through `OutputSpec`.
