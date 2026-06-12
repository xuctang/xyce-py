# Public topology representation

`CircuitGraph.G` and `CircuitGraph.spice_directives` remain visible because `xyce-py` treats the NetworkX circuit topology and SPICE directive list as advanced user-facing representations, not hidden implementation state. Public helpers own normal construction and validation, while direct topology access is reserved for callers that intentionally need NetworkX inspection or explicit `NetlistCompiler` use.
