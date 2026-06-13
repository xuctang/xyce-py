from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
import sys

import pytest

from xyce_py.features import (
    AdmsWorkflowSpec,
    XdmWorkflowSpec,
    XyceAnalysisSpec,
    XyceDeviceSpec,
    XyceDirectiveSpec,
    XyceFeatureConfig,
    XyceModelSpec,
    XyceOutputSpec,
    XyceReportSpec,
    XyceWorkflowError,
    XyceWorkflowResult,
    XyceWorkflowSpec,
)
from xyce_py.outputs import OutputSpec


pytestmark = pytest.mark.unit


class DuplicateParameterMapping(Mapping):
    def __iter__(self) -> Iterator[str]:
        return iter(("GAIN", "GAIN"))

    def __len__(self) -> int:
        return 2

    def __getitem__(self, key: str) -> str:
        if key != "GAIN":
            raise KeyError(key)
        return "1"

    def items(self):
        return (("GAIN", "1"), ("GAIN", "2"))


def test_directive_spec_emits_exact_line_with_positional_parameters_and_expression():
    directive = XyceDirectiveSpec(
        ".STEP",
        positional=["PARAM", "RLOAD", "1k", "10k", "1k"],
        parameters={"LIMIT": 4},
        expression="SWEEP DATA=load_table",
    )

    assert directive.to_spice() == ".STEP PARAM RLOAD 1k 10k 1k LIMIT=4.0 SWEEP DATA=load_table"


def test_analysis_spec_emits_major_analysis_examples():
    specs = [
        XyceAnalysisSpec(".NOISE", ["V(out)", "V1", "DEC", "10", "1", "1e6"]),
        XyceAnalysisSpec(".HB", ["FREQ", "1e9"], {"NUMFREQ": 5}),
        XyceAnalysisSpec(".SENS", ["OBJFUNC=V(out)"]),
        XyceAnalysisSpec(".FOUR", ["1k", "V(out)"]),
        XyceAnalysisSpec(".STEP", ["PARAM", "RLOAD", "1k", "10k", "1k"]),
    ]

    assert [spec.to_spice() for spec in specs] == [
        ".NOISE V(out) V1 DEC 10 1 1e6",
        ".HB FREQ 1e9 NUMFREQ=5.0",
        ".SENS OBJFUNC=V(out)",
        ".FOUR 1k V(out)",
        ".STEP PARAM RLOAD 1k 10k 1k",
    ]


def test_model_spec_emits_model_line_with_and_without_parameters():
    assert XyceModelSpec("DFAST", "D").to_spice() == ".MODEL DFAST D"
    assert (
        XyceModelSpec("NMOS_FAST", "NMOS", {"LEVEL": 1, "VTO": "0.7"}).to_spice()
        == ".MODEL NMOS_FAST NMOS(LEVEL=1.0 VTO=0.7)"
    )


def test_device_spec_emits_arbitrary_exact_device_instance_line():
    device = XyceDeviceSpec(
        "YADC1",
        nodes=["AIN", "CLK", "DOUT", "0"],
        model_name="ADC_MODEL",
        parameters={"BITS": 12},
        expression="SCHEDULE FILE=stimulus.csv",
    )

    assert (
        device.to_spice()
        == "YADC1 AIN CLK DOUT 0 ADC_MODEL BITS=12.0 SCHEDULE FILE=stimulus.csv"
    )


def test_output_and_report_specs_emit_print_lines_and_collection_specs():
    output = XyceOutputSpec(
        "noise",
        "noise",
        ["ONOISE", "INOISE"],
        "reports/noise.csv",
        output_format="csv",
    )
    report = XyceReportSpec("summary", "reports/summary.txt", kind="text", required=False)

    assert output.to_spice() == ".PRINT NOISE FORMAT=CSV FILE=reports/noise.csv ONOISE INOISE"
    assert output.output_spec() == OutputSpec.csv("noise", "reports/noise.csv")
    assert report.output_spec() == OutputSpec.text("summary", "reports/summary.txt", required=False)


def test_feature_config_from_mapping_builds_ordered_directive_lines_and_outputs():
    config = XyceFeatureConfig.from_mapping(
        {
            "directives": [
                {"directive": ".PARAM", "positional": ["RLOAD=1k"]},
            ],
            "models": [
                {"model_name": "DFAST", "model_type": "D", "parameters": {"IS": "1e-12"}},
            ],
            "devices": [
                {"device_name": "D1", "nodes": ["out", "0"], "model_name": "DFAST"},
            ],
            "analyses": [
                {"directive": ".OP"},
            ],
            "outputs": [
                {
                    "name": "operating_point",
                    "analysis_type": "dc",
                    "variables": ["V(out)"],
                    "file": "op.csv",
                },
            ],
            "reports": [
                {"name": "measurements", "path": "op.mt0", "kind": "text"},
            ],
            "workflows": [
                {"executable": "xdm", "arguments": ["--help"]},
            ],
        }
    )

    assert config.directive_lines() == (
        ".PARAM RLOAD=1k",
        ".MODEL DFAST D(IS=1e-12)",
        "D1 out 0 DFAST",
        ".OP",
        ".PRINT DC FORMAT=CSV FILE=op.csv V(out)",
    )
    assert config.output_specs() == (
        OutputSpec.csv("operating_point", "op.csv"),
        OutputSpec.text("measurements", "op.mt0"),
    )
    assert config.workflows[0].to_command() == ("xdm", "--help")


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: XyceDirectiveSpec("OP"), "directive must start with"),
        (lambda: XyceDirectiveSpec(".END"), "must not be '.END'"),
        (lambda: XyceDirectiveSpec(".STEP", "PARAM"), "positional must be provided"),
        (lambda: XyceDirectiveSpec(".STEP", [""], None), "positional item must be a non-empty"),
        (lambda: XyceDirectiveSpec(".OPTIONS", [], ["bad"]), "parameters must be a mapping"),
        (lambda: XyceDirectiveSpec(".OPTIONS", [], {"BAD KEY": "1"}), "parameters key"),
        (
            lambda: XyceDirectiveSpec(".OPTIONS", [], DuplicateParameterMapping()),
            "Duplicate parameter",
        ),
        (lambda: XyceDirectiveSpec(".PARAM", [], {"A": True}), "parameters value"),
        (lambda: XyceModelSpec("BAD NAME", "D"), "model_name must be a single"),
        (lambda: XyceDeviceSpec("R1", [], None), "nodes must be a non-empty"),
        (lambda: XyceDeviceSpec("R1", ["node with space"], None), "nodes item must be a single"),
        (lambda: XyceOutputSpec("out", ".TRAN", ["V(1)"], "out.csv"), "analysis_type"),
        (lambda: XyceOutputSpec("out", "TRAN", [], "out.csv"), "variables must be a non-empty"),
        (lambda: XyceOutputSpec("out", "TRAN", ["V(1)"], "../out.csv"), "cannot contain '..'"),
        (lambda: XyceOutputSpec("out", "TRAN", ["V(1)"], "out.csv", kind="raw"), "kind"),
        (lambda: XyceReportSpec("report", ".", "text"), "must point to a file"),
        (lambda: XyceReportSpec("report", "report.txt", "text", required="yes"), "required"),
        (lambda: XyceWorkflowSpec("", []), "executable must be a non-empty"),
        (lambda: XyceWorkflowSpec("tool", "arg"), "arguments must be provided"),
        (lambda: XyceWorkflowSpec("tool", [], working_dir=1), "working_dir"),
        (lambda: XyceWorkflowSpec("tool", [], expected_outputs=["bad"]), "expected_outputs items"),
        (lambda: XyceFeatureConfig(directives="bad"), "directives must be a list or tuple"),
        (lambda: XyceFeatureConfig(workflows="bad"), "workflows must be a list or tuple"),
        (lambda: XyceFeatureConfig(workflows=["bad"]), "workflows items"),
    ],
)
def test_feature_specs_reject_invalid_contracts(factory, message):
    with pytest.raises((TypeError, ValueError), match=message):
        factory()


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: XyceDirectiveSpec.from_mapping([]), "XyceDirectiveSpec must be a mapping"),
        (
            lambda: XyceDirectiveSpec.from_mapping({"directive": ".OP", "extra": "bad"}),
            "unknown keys",
        ),
        (lambda: XyceDirectiveSpec.from_mapping({}), "directive"),
        (lambda: XyceModelSpec.from_mapping({"model_name": "M"}), "model_type"),
        (lambda: XyceDeviceSpec.from_mapping({"device_name": "R1"}), "nodes"),
        (lambda: XyceOutputSpec.from_mapping({"name": "out"}), "analysis_type"),
        (lambda: XyceReportSpec.from_mapping({"path": "out.txt"}), "name"),
        (lambda: XyceWorkflowSpec.from_mapping({"arguments": []}), "executable"),
        (lambda: XdmWorkflowSpec.from_mapping({"unexpected": True}), "unknown keys"),
        (lambda: AdmsWorkflowSpec.from_mapping({"unexpected": True}), "unknown keys"),
        (lambda: XyceFeatureConfig.from_mapping({"unknown": []}), "unknown keys"),
    ],
)
def test_feature_specs_reject_invalid_mapping_contracts(factory, message):
    with pytest.raises((KeyError, TypeError, ValueError), match=message):
        factory()


def test_feature_config_rejects_duplicate_output_names():
    with pytest.raises(ValueError, match="Duplicate output spec name"):
        XyceFeatureConfig(
            outputs=[
                XyceOutputSpec("same", "TRAN", ["V(1)"], "one.csv"),
                XyceOutputSpec("same", "TRAN", ["V(2)"], "two.csv"),
            ]
        )


def test_feature_config_treats_none_sections_as_empty():
    config = XyceFeatureConfig(directives=None, workflows=None)

    assert config.directive_lines() == ()
    assert config.workflows == ()


def test_feature_config_accepts_workflow_instances():
    workflow = XyceWorkflowSpec("tool", [])
    config = XyceFeatureConfig(workflows=[workflow])

    assert config.workflows == (workflow,)


def test_workflow_spec_runs_command_and_collects_expected_outputs(tmp_path):
    command = (
        "from pathlib import Path; "
        "Path('workflow.txt').write_text('ok'); "
        "print('stdout marker')"
    )
    workflow = XyceWorkflowSpec(
        sys.executable,
        ["-c", command],
        working_dir=tmp_path,
        expected_outputs=[XyceReportSpec("workflow", "workflow.txt")],
    )

    result = workflow.run()

    assert isinstance(result, XyceWorkflowResult)
    assert result.command == (sys.executable, "-c", command)
    assert result.working_dir == tmp_path.resolve()
    assert "stdout marker" in result.stdout
    assert result.outputs["workflow"].text == "ok"


def test_workflow_spec_uses_current_directory_when_working_dir_is_none():
    workflow = XyceWorkflowSpec(sys.executable, ["-c", "print('cwd ok')"])

    result = workflow.run()

    assert result.working_dir == Path.cwd()
    assert "cwd ok" in result.stdout


def test_workflow_spec_raises_structured_error_for_failed_command(tmp_path):
    workflow = XyceWorkflowSpec(
        sys.executable,
        ["-c", "import sys; print('bad', file=sys.stderr); sys.exit(7)"],
        working_dir=tmp_path,
    )

    with pytest.raises(XyceWorkflowError) as exc_info:
        workflow.run()

    assert exc_info.value.command[:2] == (sys.executable, "-c")
    assert exc_info.value.returncode == 7
    assert "bad" in exc_info.value.stderr
    assert exc_info.value.working_dir == tmp_path.resolve()


def test_workflow_spec_rejects_missing_working_dir_and_missing_expected_output(tmp_path):
    missing_dir = tmp_path / "missing"
    with pytest.raises(FileNotFoundError, match="working_dir does not exist"):
        XyceWorkflowSpec(sys.executable, ["-c", "print('ok')"], working_dir=missing_dir).run()

    not_directory = tmp_path / "not-directory"
    not_directory.write_text("not a directory")
    with pytest.raises(NotADirectoryError, match="working_dir must be a directory"):
        XyceWorkflowSpec(sys.executable, ["-c", "print('ok')"], working_dir=not_directory).run()

    workflow = XyceWorkflowSpec(
        sys.executable,
        ["-c", "print('ok')"],
        working_dir=tmp_path,
        expected_outputs=[XyceReportSpec("missing", "missing.txt")],
    )
    with pytest.raises(FileNotFoundError, match="Required Xyce output"):
        workflow.run()


def test_xdm_and_adms_workflow_specs_provide_defaults_and_mapping_overrides(tmp_path):
    xdm = XdmWorkflowSpec.from_mapping({"arguments": ["in.cir"], "working_dir": tmp_path})
    adms = AdmsWorkflowSpec.from_mapping(
        {"executable": "custom-adms", "arguments": ["model.va"], "working_dir": tmp_path}
    )

    assert xdm.to_command() == ("xdm", "in.cir")
    assert adms.to_command() == ("custom-adms", "model.va")
    assert Path(xdm.working_dir) == tmp_path
