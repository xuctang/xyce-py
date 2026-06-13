# Raw netlist project interface

`XyceProject` is the raw-netlist interface for callers who already know Xyce syntax or need analysis/device coverage that is not yet modeled by `CircuitGraph`. It carries exact netlist text to Xyce, declares expected output specs explicitly, and leaves Xyce responsible for parsing advanced directives. This keeps `CircuitGraph` focused on topology-based Python construction while giving advanced Xyce users a deeper module for exact netlist execution.
