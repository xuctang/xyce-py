from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import xyce_py.cli as cli
from xyce_py.engine import XyceExecutionResult, XyceRunError
from xyce_py.netlists import XyceProjectResult
from xyce_py.outputs import OutputArtifact, OutputSpec


pytestmark = pytest.mark.unit


class _FakeProject:
    def __init__(self, name: str, result: XyceProjectResult | None = None, error: XyceRunError | None = None):
        self.name = name
        self.result = result
        self.error = error
        self.run_calls: list[dict[str, object]] = []

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _fake_result(tmp_path: Path) -> XyceProjectResult:
    output_spec = OutputSpec.csv("waveforms", "out.csv")
    output_artifact = OutputArtifact(
        spec=output_spec,
        path=tmp_path / "run" / "out.csv",
        exists=True,
        frame=pd.DataFrame({"TIME": [0.0], "V(1)": [1.0]}),
    )
    execution = XyceExecutionResult(
        run_dir=tmp_path / "run",
        netlist_path=tmp_path / "run" / "circuit.cir",
        stdout="xyce stdout",
        stderr="xyce stderr",
        waveforms=pd.DataFrame({"TIME": [0.0]}),
        solve_time_sec=0.25,
    )
    return XyceProjectResult(execution=execution, outputs={"waveforms": output_artifact})


def test_cli_run_builds_project_from_file_and_prints_json_summary(monkeypatch, tmp_path, capsys):
    netlist_path = tmp_path / "case.cir"
    netlist_path.write_text("* test\n.END\n")
    fake_project = _FakeProject("case", result=_fake_result(tmp_path))
    captured_from_file: dict[str, object] = {}

    def _fake_from_file(path, *, output_specs, name=None):
        captured_from_file["path"] = path
        captured_from_file["output_specs"] = tuple(output_specs)
        captured_from_file["name"] = name
        return fake_project

    monkeypatch.setattr(cli.XyceProject, "from_file", staticmethod(_fake_from_file))

    exit_code = cli.main(
        [
            "run",
            str(netlist_path),
            "--name",
            "case",
            "--xyce-path",
            "/opt/Xyce",
            "--base-out-dir",
            str(tmp_path / "runs"),
            "--run-name",
            "run-1",
            "--csv-output",
            "waveforms",
            "out.csv",
            "--optional-text-output",
            "measurements",
            "measure.txt",
        ]
    )

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert exit_code == 0
    assert captured_from_file["path"] == netlist_path
    assert captured_from_file["name"] == "case"
    assert captured_from_file["output_specs"] == (
        OutputSpec.csv("waveforms", "out.csv"),
        OutputSpec.text("measurements", "measure.txt", required=False),
    )
    assert fake_project.run_calls == [
        {
            "xyce_path": "/opt/Xyce",
            "base_out_dir": str(tmp_path / "runs"),
            "run_name": "run-1",
            "target_dir": None,
            "keep_run_dir": True,
        }
    ]
    assert payload["project"] == "case"
    assert payload["outputs"]["waveforms"]["rows"] == 1
    assert payload["outputs"]["waveforms"]["columns"] == ["TIME", "V(1)"]
    assert payload["stdout"] == "xyce stdout"
    assert payload["stderr"] == "xyce stderr"


def test_cli_run_can_discard_run_dir_and_use_target_dir(monkeypatch, tmp_path):
    netlist_path = tmp_path / "case.cir"
    netlist_path.write_text("* test\n.END\n")
    fake_project = _FakeProject("case", result=_fake_result(tmp_path))
    monkeypatch.setattr(cli.XyceProject, "from_file", staticmethod(lambda *args, **kwargs: fake_project))

    exit_code = cli.main(
        [
            "run",
            str(netlist_path),
            "--target-dir",
            str(tmp_path / "exact-run"),
            "--discard-run-dir",
        ]
    )

    assert exit_code == 0
    assert fake_project.run_calls[0]["target_dir"] == tmp_path / "exact-run"
    assert fake_project.run_calls[0]["keep_run_dir"] is False


def test_cli_run_returns_xyce_error_code_and_writes_error(monkeypatch, tmp_path, capsys):
    netlist_path = tmp_path / "case.cir"
    netlist_path.write_text("* test\n.END\n")
    fake_project = _FakeProject("case", error=XyceRunError("solver failed", returncode=7))
    monkeypatch.setattr(cli.XyceProject, "from_file", staticmethod(lambda *args, **kwargs: fake_project))

    exit_code = cli.main(["run", str(netlist_path)])

    captured = capsys.readouterr()
    assert exit_code == 7
    assert "solver failed" in captured.err
    assert captured.out == ""
