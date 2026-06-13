from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import xyce_py.netlists as netlists
from xyce_py.engine import XyceExecutionResult, XyceRunError
from xyce_py.netlists import XyceProject, XyceProjectResult
from xyce_py.outputs import OutputSpec


pytestmark = pytest.mark.unit


RAW_NETLIST = """* raw voltage divider
V1 1 0 DC 5
R1 1 2 1000
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=output.csv V(1) V(2)
.END
"""


def _fake_execution(run_dir: Path) -> XyceExecutionResult:
    return XyceExecutionResult(
        run_dir=run_dir,
        netlist_path=run_dir / "circuit.cir",
        stdout="solver stdout",
        stderr="solver stderr",
        waveforms=pd.DataFrame({"V(1)": [5.0]}),
        solve_time_sec=0.25,
    )


def test_xyce_project_rejects_empty_or_unterminated_netlists():
    with pytest.raises(ValueError, match="netlist_content must be a non-empty string"):
        XyceProject("raw", "")

    with pytest.raises(ValueError, match="must contain a top-level '.END' line"):
        XyceProject("raw", "* missing end\nR1 1 0 1k\n")

    with pytest.raises(ValueError, match="must contain a top-level '.END' line"):
        XyceProject("raw", "* .END in comment only\nR1 1 0 1k\n")


def test_xyce_project_from_file_reads_exact_netlist_content(tmp_path):
    netlist_path = tmp_path / "input.cir"
    netlist_path.write_text(RAW_NETLIST)

    project = XyceProject.from_file(
        netlist_path,
        output_specs=[OutputSpec.csv("waveforms", "output.csv")],
    )

    assert project.name == "input"
    assert project.netlist_content == RAW_NETLIST
    assert project.output_specs == (OutputSpec.csv("waveforms", "output.csv"),)


def test_xyce_project_from_file_accepts_explicit_name(tmp_path):
    netlist_path = tmp_path / "input.cir"
    netlist_path.write_text(RAW_NETLIST)

    project = XyceProject.from_file(netlist_path, name="release-smoke")

    assert project.name == "release-smoke"


def test_xyce_project_rejects_duplicate_output_spec_names():
    with pytest.raises(ValueError, match="Duplicate output spec name"):
        XyceProject(
            "raw",
            RAW_NETLIST,
            output_specs=(
                OutputSpec.csv("waveforms", "one.csv"),
                OutputSpec.text("waveforms", "two.txt"),
            ),
        )


def test_xyce_project_run_invokes_engine_with_exact_raw_netlist_and_collects_outputs(
    monkeypatch,
    tmp_path,
):
    captured: dict[str, object] = {}

    def _fake_run_xyce_netlist(**kwargs):
        captured.update(kwargs)
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "output.csv").write_text("TIME,V(1),V(2)\n0.0,5.0,2.5\n")
        (run_dir / "measure.txt").write_text("gain = 0.5\n")
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject(
        "raw-run",
        RAW_NETLIST,
        output_specs=(
            OutputSpec.csv("waveforms", "output.csv"),
            OutputSpec.text("measurements", "measure.txt"),
        ),
    )

    result = project.run(xyce_path="/opt/Xyce", base_out_dir=tmp_path, keep_run_dir=True)

    assert isinstance(result, XyceProjectResult)
    assert captured["xyce_path"] == "/opt/Xyce"
    assert captured["netlist_content"] == RAW_NETLIST
    assert captured["csv_name"] == "output.csv"
    assert captured["keep_run_dir"] is True
    assert captured["run_name"] == "raw-run"
    assert_frame_equal(
        result.outputs["waveforms"].frame,
        pd.DataFrame({"TIME": [0.0], "V(1)": [5.0], "V(2)": [2.5]}),
    )
    assert result.output("measurements").text == "gain = 0.5\n"
    assert result.stdout == "solver stdout"
    assert result.stderr == "solver stderr"
    assert result.solve_time_sec == 0.25


def test_xyce_project_result_outputs_are_read_only(tmp_path):
    execution = _fake_execution(tmp_path)
    result = XyceProjectResult(execution=execution, outputs={})

    with pytest.raises(TypeError):
        result.outputs["waveforms"] = object()


def test_xyce_project_result_parses_measurement_text_output(tmp_path):
    execution = _fake_execution(tmp_path)
    result = XyceProjectResult(
        execution=execution,
        outputs={
            "measurements": netlists.OutputArtifact(
                spec=OutputSpec.text("measurements", "circuit.cir.mt0"),
                path=tmp_path / "circuit.cir.mt0",
                exists=True,
                text="GAIN = 5.000000e-01\n",
            )
        },
    )

    assert result.measurements()["GAIN"].value == 0.5


def test_xyce_project_result_measurements_rejects_non_text_output(tmp_path):
    execution = _fake_execution(tmp_path)
    result = XyceProjectResult(
        execution=execution,
        outputs={
            "waveforms": netlists.OutputArtifact(
                spec=OutputSpec.csv("waveforms", "output.csv"),
                path=tmp_path / "output.csv",
                exists=True,
                frame=pd.DataFrame({"V(1)": [1.0]}),
            )
        },
    )

    with pytest.raises(TypeError, match="is not a text output artifact"):
        result.measurements("waveforms")


def test_xyce_project_run_uses_first_csv_output_as_engine_waveform_file(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def _fake_run_xyce_netlist(**kwargs):
        captured.update(kwargs)
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "main.prn").write_text("text\n")
        (run_dir / "nested").mkdir()
        (run_dir / "nested" / "waveforms.csv").write_text("TIME,V(1)\n0.0,1.0\n")
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject(
        "raw-run",
        RAW_NETLIST,
        output_specs=(
            OutputSpec.text("listing", "main.prn"),
            OutputSpec.csv("waveforms", "nested/waveforms.csv"),
        ),
    )

    project.run(base_out_dir=tmp_path)

    assert captured["csv_name"] == "nested/waveforms.csv"


def test_xyce_project_run_defaults_to_output_csv_when_no_csv_output_specs(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def _fake_run_xyce_netlist(**kwargs):
        captured.update(kwargs)
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "measure.txt").write_text("gain = 0.5\n")
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject("raw-run", RAW_NETLIST, output_specs=(OutputSpec.text("measure", "measure.txt"),))

    project.run(base_out_dir=tmp_path)

    assert captured["csv_name"] == "output.csv"


def test_xyce_project_run_keeps_artifacts_by_default(monkeypatch, tmp_path):
    def _fake_run_xyce_netlist(**kwargs):
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "output.csv").write_text("TIME,V(1)\n0.0,1.0\n")
        (run_dir / "output.prn").write_text("prn")
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)

    result = XyceProject("raw-run", RAW_NETLIST, (OutputSpec.csv("waveforms", "output.csv"),)).run(
        base_out_dir=tmp_path
    )

    assert result.execution.netlist_path.exists()
    assert (result.run_dir / "output.csv").exists()
    assert (result.run_dir / "output.prn").exists()


def test_xyce_project_run_removes_declared_artifacts_when_keep_run_dir_is_false(monkeypatch, tmp_path):
    def _fake_run_xyce_netlist(**kwargs):
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "output.csv").write_text("TIME,V(1)\n0.0,1.0\n")
        (run_dir / "output.prn").write_text("prn")
        (run_dir / "measure.txt").write_text("gain = 0.5\n")
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject(
        "raw-run",
        RAW_NETLIST,
        (
            OutputSpec.csv("waveforms", "output.csv"),
            OutputSpec.text("measure", "measure.txt"),
        ),
    )

    result = project.run(base_out_dir=tmp_path, keep_run_dir=False)

    assert not result.execution.netlist_path.exists()
    assert not (result.run_dir / "output.csv").exists()
    assert not (result.run_dir / "output.prn").exists()
    assert not (result.run_dir / "measure.txt").exists()
    assert result.outputs["waveforms"].frame.iloc[0]["V(1)"] == 1.0
    assert result.outputs["measure"].text == "gain = 0.5\n"


def test_xyce_project_run_preserves_artifacts_when_required_output_is_missing(monkeypatch, tmp_path):
    def _fake_run_xyce_netlist(**kwargs):
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject("raw-run", RAW_NETLIST, (OutputSpec.csv("waveforms", "missing.csv"),))

    with pytest.raises(FileNotFoundError, match="Required Xyce output 'waveforms'"):
        project.run(base_out_dir=tmp_path, keep_run_dir=False)

    assert (tmp_path / "raw-run" / "circuit.cir").exists()


def test_xyce_project_run_records_optional_missing_outputs(monkeypatch, tmp_path):
    def _fake_run_xyce_netlist(**kwargs):
        run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
        run_dir.mkdir(parents=True)
        (run_dir / "circuit.cir").write_text(kwargs["netlist_content"])
        return _fake_execution(run_dir)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _fake_run_xyce_netlist)
    project = XyceProject(
        "raw-run",
        RAW_NETLIST,
        (OutputSpec.csv("waveforms", "missing.csv", required=False),),
    )

    result = project.run(base_out_dir=tmp_path)

    assert result.outputs["waveforms"].exists is False
    assert result.outputs["waveforms"].frame is None


def test_xyce_project_run_propagates_xyce_run_errors_without_collecting_outputs(monkeypatch, tmp_path):
    def _raise_error(**kwargs):
        raise XyceRunError("solver failed", returncode=1)

    monkeypatch.setattr(netlists, "run_xyce_netlist", _raise_error)
    project = XyceProject("raw-run", RAW_NETLIST, (OutputSpec.csv("waveforms", "output.csv"),))

    with pytest.raises(XyceRunError, match="solver failed"):
        project.run(base_out_dir=tmp_path)


def test_xyce_project_run_validates_run_name_and_keep_run_dir(monkeypatch, tmp_path):
    project = XyceProject("raw-run", RAW_NETLIST)

    with pytest.raises(ValueError, match="run_name must be a non-empty string"):
        project.run(base_out_dir=tmp_path, run_name=" ")

    with pytest.raises(TypeError, match="keep_run_dir must be a boolean"):
        project.run(base_out_dir=tmp_path, keep_run_dir="yes")
