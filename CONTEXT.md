# xyce-py Context

This context defines the circuit-simulation language used by `xyce-py`. The package builds circuit topology in Python, compiles it to a Xyce netlist, runs Xyce, and returns waveform results.

## Language

**CircuitGraph**:
The user-facing circuit topology module backed by a NetworkX graph. It owns graph construction, topology validation, simulation request normalization, and solve-result assembly.
_Avoid_: graph wrapper, circuit builder

**Circuit topology**:
The directed graph of user nodes, branches, multi-terminal devices, and grounding metadata that represents a circuit before netlist compilation.
_Avoid_: network, schematic

**User node**:
A caller-provided, hashable circuit node identifier. User nodes are mapped to generated SPICE node names during compilation.
_Avoid_: bus, vertex

**Ground node**:
The single user node marked as the circuit ground reference. It compiles to SPICE node `0`.
_Avoid_: reference vertex, zero node

**Branch**:
A two-terminal connection between user nodes containing one or more two-terminal circuit elements in series.
_Avoid_: edge, wire

**Device**:
A multi-terminal circuit element represented by an internal device node and ordered terminal links in the topology.
_Avoid_: component, part

**SPICE directive**:
Raw netlist text for Xyce features such as `.MODEL`, `.OPTIONS`, and `.SUBCKT` that is carried through without parsing internals.
_Avoid_: command, config line

**Netlist body**:
The compiled netlist lines before simulation analysis directives, `.PRINT`, and `.END` are appended.
_Avoid_: partial netlist, template

**Xyce execution**:
The subprocess run that writes a netlist, invokes Xyce, reads waveform CSV output, and reports execution failures.
_Avoid_: solver call, run wrapper

**Waveform result**:
The Pandas dataframe and related solve metadata returned from Xyce output.
_Avoid_: output table, result data
