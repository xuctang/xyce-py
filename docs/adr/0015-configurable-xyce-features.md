# Configurable Xyce feature specs

`xyce-py` needs to support the full Xyce feature surface without pretending to
own Xyce's simulator grammar. Xyce contains many analysis directives, device and
model families, solver options, output/report modes, XDM flows, and ADMS model
development flows. Recreating all of those semantics as typed Python classes
would be brittle and would duplicate the simulator.

The supported boundary is a configurable feature layer:

- `XyceDirectiveSpec` and `XyceAnalysisSpec` emit exact directive lines.
- `XyceModelSpec` and `XyceDeviceSpec` emit exact model and device lines.
- `XyceOutputSpec` emits `.PRINT` lines and declares output artifacts.
- `XyceReportSpec` declares report artifacts that should be collected.
- `XyceFeatureConfig` groups specs into stable project inputs.
- `XyceWorkflowSpec`, `XdmWorkflowSpec`, and `AdmsWorkflowSpec` run external
  tool workflows with structured stdout/stderr and output collection.

The package validates Python-side contracts only: non-empty strings, single
netlist tokens where a field is explicitly a token, list/mapping shape, safe
relative output paths, duplicate output names, and package-owned `.END`
insertion. It does not validate whether a `.HB` argument, device parameter, or
model option is meaningful to a particular Xyce version.

This keeps module boundaries explicit:

- Graph topology remains owned by `CircuitGraph` and `NetlistCompiler`.
- Exact simulator feature text is owned by `xyce_py.features`.
- Raw project execution and output collection remain owned by `XyceProject` and
  `OutputSpec`.
- Xyce and external tools remain the semantic authority for feature syntax.

Typed convenience classes can still be added later when they provide a stable
Python contract with real value. They should emit through the same exact-text
boundary rather than adding a second simulator grammar.
