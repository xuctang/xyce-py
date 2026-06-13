# Configurable Xyce Features

`xyce-py` supports every Xyce feature category through configurable specs that
emit exact netlist lines or exact external command invocations. The package
validates Python-side shape, relative output paths, duplicate output names, and
`.END` ownership. Xyce remains the parser and authority for simulator semantics.

Use these specs when a feature should be easy to configure but does not justify
a custom Python class for every Xyce directive, device family, model family, or
report mode.

## Graph-compiled project

```python
from xyce_py import (
    CircuitGraph,
    OutputSpec,
    Resistor,
    VoltageSource,
    XyceAnalysisSpec,
    XyceFeatureConfig,
    XyceOutputSpec,
)

graph = CircuitGraph(xyce_path="Xyce")
graph.add_node("gnd", is_ground=True)
graph.add_branch("vin", "gnd", [VoltageSource("supply", 5.0)])
graph.add_branch("vin", "vout", [Resistor("load", 1000)])

body = graph.compile_body()
vout = body.user_to_spice_node["vout"]

config = XyceFeatureConfig(
    analyses=[
        XyceAnalysisSpec(".NOISE", [f"V({vout})", "V_supply", "DEC", "10", "1", "1e6"]),
    ],
    outputs=[
        XyceOutputSpec("noise", "NOISE", ["ONOISE", "INOISE"], "noise.csv"),
    ],
)

project = graph.compile_project(
    "noise-analysis",
    config.directive_lines(),
    output_specs=config.output_specs(),
)
result = project.run(xyce_path="Xyce")
print(result.outputs["noise"].frame)
```

`compile_body()` exposes generated SPICE node names. Configurable raw device
and analysis lines should use those generated names when they refer to graph
nodes.

## Analysis directives

```python
from xyce_py import XyceAnalysisSpec

noise = XyceAnalysisSpec(".NOISE", ["V(out)", "V1", "DEC", "10", "1", "1e6"])
hb = XyceAnalysisSpec(".HB", ["FREQ", "1e9"], {"NUMFREQ": 5})
sens = XyceAnalysisSpec(".SENS", ["OBJFUNC=V(out)"])
four = XyceAnalysisSpec(".FOUR", ["1k", "V(out)"])
step = XyceAnalysisSpec(".STEP", ["PARAM", "RLOAD", "1k", "10k", "1k"])

assert noise.to_spice() == ".NOISE V(out) V1 DEC 10 1 1e6"
```

The same object shape works for any Xyce directive token, including directives
added by newer Xyce releases.

## Devices and models

```python
from xyce_py import XyceDeviceSpec, XyceModelSpec

model = XyceModelSpec("DFAST", "D", {"IS": "1e-12"})
device = XyceDeviceSpec("D1", ["out", "0"], model_name="DFAST")

assert model.to_spice() == ".MODEL DFAST D(IS=1e-12)"
assert device.to_spice() == "D1 out 0 DFAST"
```

`XyceDeviceSpec.device_name` is the exact Xyce instance token. The wrapper does
not inject a prefix, suffix, or naming convention.

## Output and reports

```python
from xyce_py import XyceOutputSpec, XyceReportSpec

waveforms = XyceOutputSpec(
    "waveforms",
    "TRAN",
    ["V(out)", "I(V1)"],
    "tran.csv",
    output_format="CSV",
    kind="csv",
)
summary = XyceReportSpec("summary", "run.log", kind="text", required=False)

assert waveforms.to_spice() == ".PRINT TRAN FORMAT=CSV FILE=tran.csv V(out) I(V1)"
output_specs = (waveforms.output_spec(), summary.output_spec())
```

`XyceOutputSpec` emits a `.PRINT` line and declares the produced artifact.
`XyceReportSpec` only declares an expected artifact for report files generated
by Xyce or an external workflow.

## Mapping configuration

```python
from xyce_py import XyceFeatureConfig

config = XyceFeatureConfig.from_mapping(
    {
        "directives": [{"directive": ".PARAM", "positional": ["RLOAD=1k"]}],
        "models": [{"model_name": "DFAST", "model_type": "D"}],
        "devices": [{"device_name": "D1", "nodes": ["out", "0"], "model_name": "DFAST"}],
        "analyses": [{"directive": ".OP"}],
        "outputs": [
            {
                "name": "operating_point",
                "analysis_type": "DC",
                "variables": ["V(out)"],
                "file": "op.csv",
            }
        ],
        "reports": [{"name": "measurements", "path": "op.mt0", "kind": "text"}],
    }
)
```

Unknown top-level keys and unknown spec keys are rejected so configuration
mistakes fail before a run is launched.

## XDM and ADMS workflows

```python
from xyce_py import AdmsWorkflowSpec, XdmWorkflowSpec, XyceReportSpec

xdm = XdmWorkflowSpec(
    arguments=["input.sp", "-o", "translated.cir"],
    expected_outputs=[XyceReportSpec("translated", "translated.cir")],
)
adms = AdmsWorkflowSpec(arguments=["model.va", "-e", "xyceVersion.xml"])

print(xdm.to_command())
print(adms.to_command())
```

Workflow specs run external commands without a shell, capture stdout/stderr, and
collect declared report artifacts. Non-zero exits raise `XyceWorkflowError`.
