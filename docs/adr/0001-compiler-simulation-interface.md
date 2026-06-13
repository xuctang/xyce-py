# Compiler simulation interface

`CircuitGraph.simulate()` uses `NetlistCompiler.compile_body()` instead of calling the compiler's private implementation method or reading mutable compiler state directly. The compiler owns netlist-body lines, user-to-SPICE and SPICE-to-user node translation tables, and the expanded graph as one interface, while `CircuitGraph` owns analysis directives, `.PRINT` assembly, Xyce execution, and `SolveResult` construction.
