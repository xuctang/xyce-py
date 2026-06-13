# Parameter sweep interface

`XyceParameterSweep` runs Python-side parameter sweeps by generating explicit `.PARAM` variants and executing each variant through `XyceProject`. It does not parse or emulate Xyce `.STEP`; raw netlists can still use native `.STEP` directly through `XyceProject`. Sweep parameters must not already be defined by `.PARAM` lines in the base netlist, because implicit overriding would make ordering and ownership unclear.
