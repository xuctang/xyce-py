# Opaque SPICE directives

`CircuitGraph` validates only the outer directive contract for `.MODEL`, `.OPTIONS`, and `.SUBCKT` text, then carries the text through to the netlist unchanged. Xyce remains responsible for parsing directive internals and diagnosing subcircuit arity or syntax errors because duplicating that parser in Python would create a second source of truth.
