# Solver options interface

`CircuitGraph.solver_params` is a package-to-options mapping that emits `.OPTIONS <package> key=value...` lines through `OptionsDirective`. `xyce-py` validates the Python-side mapping shape and directive tokens, but it does not maintain a catalog of valid Xyce option packages or option names. The compiler emits its built-in `.OPTIONS DEVICE GMIN=1e-8` line before caller-provided `.OPTIONS` directives so explicit caller options remain visible later in the netlist.
