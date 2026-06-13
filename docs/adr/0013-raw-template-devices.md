# Raw template devices

`RawTwoTerminalElement` and `RawNTerminalDevice` are graph-level adapters for Xyce device syntax that is not modeled by typed Python classes. They substitute topology-owned SPICE node names into caller-owned `string.Template` text, then pass the resulting element line directly to Xyce.

The package does not parse or validate Xyce device semantics here. It validates only the Python-side contract: required node placeholders must be present, unknown template placeholders are rejected, terminal arity must match, and mapped nodes must be valid strings. Xyce remains the authority for whether the final element line is physically and syntactically valid.

This keeps the boundary explicit: typed model classes cover common devices, raw template devices provide an exact escape hatch for advanced Xyce elements inside `CircuitGraph`, and `XyceProject` remains the interface for fully raw netlists.
