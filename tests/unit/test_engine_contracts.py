from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import xyce_py.engine as engine
from xyce_py.engine import XyceRunError, execute_xyce_netlist, _read_waveforms


pytestmark = pytest.mark.unit


def _completed_process(*, returncode: int = 0, stdout: str = "stdout", stderr: str = "stderr"):
    return subprocess.CompletedProcess(args=["Xyce", "circuit.cir"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_execute_xyce_netlist_invokes_subprocess_with_exact_contract(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def _fake_run(args, cwd, capture_output, text):
        captured.update(
            {
                "args": args,
                "cwd": cwd,
                "capture_output": capture_output,
                "text": text,
            }
        )
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    execute_xyce_netlist(
        xyce_path="/opt/Xyce/bin/Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="contract",
        keep_run_dir=True,
    )

    assert captured == {
        "args": ["/opt/Xyce/bin/Xyce", "circuit.cir"],
        "cwd": tmp_path / "contract",
        "capture_output": True,
        "text": True,
    }


def test_execute_xyce_netlist_resolves_relative_base_out_dir(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = execute_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir="relative_runs",
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="run1",
        keep_run_dir=True,
    )

    assert result.run_dir == tmp_path / "relative_runs" / "run1"
    assert result.netlist_path == tmp_path / "relative_runs" / "run1" / "circuit.cir"


def test_execute_xyce_netlist_records_elapsed_subprocess_time(monkeypatch, tmp_path):
    times = iter([100.0, 102.25])

    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)
    monkeypatch.setattr(engine.time, "perf_counter", lambda: next(times))

    result = execute_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
    )

    assert result.solve_time_sec == 2.25


def test_execute_xyce_netlist_does_not_read_waveforms_after_xyce_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.subprocess, "run", lambda *args, **kwargs: _completed_process(returncode=9))
    monkeypatch.setattr(
        engine,
        "_read_waveforms",
        lambda path: (_ for _ in ()).throw(AssertionError("waveforms must not be read")),
    )

    with pytest.raises(XyceRunError):
        execute_xyce_netlist(
            xyce_path="Xyce",
            base_out_dir=tmp_path,
            netlist_content="* test\n.END\n",
            csv_name="output.csv",
            keep_run_dir=False,
        )


def test_execute_xyce_netlist_preserves_failure_artifacts_even_when_cleanup_was_requested(monkeypatch, tmp_path):
    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        return _completed_process(returncode=2, stdout="bad netlist", stderr="details")

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    with pytest.raises(XyceRunError) as exc_info:
        execute_xyce_netlist(
            xyce_path="Xyce",
            base_out_dir=tmp_path,
            netlist_content="* test\n.END\n",
            csv_name="output.csv",
            run_name="failure",
            keep_run_dir=False,
        )

    assert exc_info.value.netlist_path.exists()
    assert exc_info.value.csv_path.exists()


def test_execute_xyce_netlist_cleanup_tolerates_missing_output_artifacts(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.subprocess, "run", lambda *args, **kwargs: _completed_process())

    result = execute_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="missing_outputs",
        keep_run_dir=False,
    )

    assert result.waveforms.empty
    assert not result.netlist_path.exists()


def test_read_waveforms_preserves_quoted_commas_and_numeric_columns(tmp_path):
    csv_path = tmp_path / "quoted.csv"
    csv_path.write_text('TIME,LABEL,V(N_1)\n0.0,"a,b",1.5\n1.0,"c,d",2.5\n')

    frame = _read_waveforms(csv_path)

    expected = pd.DataFrame({"TIME": [0.0, 1.0], "LABEL": ["a,b", "c,d"], "V(N_1)": [1.5, 2.5]})
    assert_frame_equal(frame, expected)


def test_xyce_run_error_preserves_optional_context_fields(tmp_path):
    error = XyceRunError(
        "failed",
        returncode=3,
        stdout="out",
        stderr="err",
        run_dir=tmp_path,
        netlist_path=tmp_path / "circuit.cir",
        csv_path=tmp_path / "output.csv",
        solve_time_sec=1.25,
    )

    assert str(error) == "failed"
    assert error.returncode == 3
    assert error.stdout == "out"
    assert error.stderr == "err"
    assert error.run_dir == tmp_path
    assert error.netlist_path == tmp_path / "circuit.cir"
    assert error.csv_path == tmp_path / "output.csv"
    assert error.solve_time_sec == 1.25
