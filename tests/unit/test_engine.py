from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest

import xyce_py.engine as engine
from xyce_py.engine import XyceRunError, run_xyce_netlist, _read_waveforms, find_xyce_executable


pytestmark = pytest.mark.unit


def _completed_process(*, returncode: int = 0, stdout: str = "stdout", stderr: str = "stderr"):
    return subprocess.CompletedProcess(args=["Xyce", "circuit.cir"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_find_xyce_executable_prefers_known_install_paths(monkeypatch):
    missing_path = Path("/missing/Xyce")
    known_path = Path("/usr/local/Xyce-Release-7.10-NORAD/bin/Xyce")
    monkeypatch.setattr(
        engine,
        "_candidate_xyce_paths",
        lambda: (
            missing_path,
            known_path,
        ),
    )
    monkeypatch.setattr(
        engine.Path,
        "exists",
        lambda self: self == known_path,
    )
    monkeypatch.setattr(engine.shutil, "which", lambda _: "/usr/bin/Xyce")

    assert find_xyce_executable() == str(known_path)


def test_candidate_xyce_paths_include_windows_program_files_on_windows(monkeypatch):
    usr_local_path = Path("/usr/local")
    program_files_path = Path("C:/Program Files")
    xyce_path = program_files_path / "Xyce" / "bin" / "Xyce.exe"

    def _fake_glob(path: Path, pattern: str):
        if path == usr_local_path:
            return []
        if path == program_files_path and pattern == "Xyce*/bin/Xyce.exe":
            return [xyce_path]
        return []

    monkeypatch.setattr(engine.sys, "platform", "win32")
    monkeypatch.setattr(engine.Path, "exists", lambda self: self == program_files_path)
    monkeypatch.setattr(engine.Path, "glob", _fake_glob)

    assert xyce_path in engine._candidate_xyce_paths()


def test_find_xyce_executable_uses_path_lookup_when_known_path_is_missing(monkeypatch):
    monkeypatch.setattr(engine, "_candidate_xyce_paths", lambda: (Path("/missing/Xyce"),))
    monkeypatch.setattr(engine.Path, "exists", lambda self: False)
    monkeypatch.setattr(engine.shutil, "which", lambda _: "/usr/bin/Xyce")

    assert find_xyce_executable() == "/usr/bin/Xyce"


def test_find_xyce_executable_returns_literal_xyce_when_nothing_is_found(monkeypatch):
    monkeypatch.setattr(engine, "_candidate_xyce_paths", lambda: (Path("/missing/Xyce"),))
    monkeypatch.setattr(engine.Path, "exists", lambda self: False)
    monkeypatch.setattr(engine.shutil, "which", lambda _: None)

    assert find_xyce_executable() == "Xyce"


def test_read_waveforms_returns_empty_dataframe_for_missing_file(tmp_path):
    frame = _read_waveforms(tmp_path / "missing.csv")

    assert frame.empty


def test_read_waveforms_returns_empty_dataframe_for_zero_byte_file(tmp_path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("")

    frame = _read_waveforms(csv_path)

    assert frame.empty


def test_read_waveforms_returns_empty_dataframe_for_header_only_csv(tmp_path):
    csv_path = tmp_path / "header_only.csv"
    csv_path.write_text("TIME,V(N_1)\n")

    frame = _read_waveforms(csv_path)

    assert frame.empty
    assert list(frame.columns) == ["TIME", "V(N_1)"]


def test_read_waveforms_returns_empty_dataframe_for_empty_data_error(tmp_path):
    csv_path = tmp_path / "blank_lines.csv"
    csv_path.write_text("\n\n")

    frame = _read_waveforms(csv_path)

    assert frame.empty


def test_read_waveforms_preserves_whitespace_in_headers(tmp_path):
    csv_path = tmp_path / "headers.csv"
    csv_path.write_text(" TIME , V(N_1) \n0.0,1.0\n")

    frame = _read_waveforms(csv_path)

    assert list(frame.columns) == [" TIME ", " V(N_1) "]


def test_read_waveforms_reads_single_and_multi_row_csv(tmp_path):
    one_row = tmp_path / "one.csv"
    one_row.write_text("TIME,V(N_1)\n0.0,1.0\n")
    multi_row = tmp_path / "multi.csv"
    multi_row.write_text("TIME,V(N_1)\n0.0,1.0\n1.0,2.0\n")

    one_frame = _read_waveforms(one_row)
    multi_frame = _read_waveforms(multi_row)

    assert one_frame.shape == (1, 2)
    assert multi_frame.shape == (2, 2)


def test_read_waveforms_propagates_parser_errors_for_malformed_csv(tmp_path):
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text('TIME,V(N_1)\n0.0,"unterminated\n')

    with pytest.raises(pd.errors.ParserError):
        _read_waveforms(csv_path)


def test_run_xyce_netlist_writes_netlist_and_returns_waveforms_stdout_and_stderr(monkeypatch, tmp_path):
    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        (Path(cwd) / "output.prn").write_text("prn")
        return _completed_process(stdout="ok", stderr="warn")

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="success",
        keep_run_dir=True,
    )

    assert result.netlist_path.read_text() == "* test\n.END\n"
    assert list(result.waveforms.columns) == ["TIME", "V(N_1)"]
    assert result.stdout == "ok"
    assert result.stderr == "warn"


def test_run_xyce_netlist_uses_target_dir_over_base_out_dir(monkeypatch, tmp_path):
    target_dir = tmp_path / "custom-target"

    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path / "ignored",
        target_dir=target_dir,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        keep_run_dir=True,
    )

    assert result.run_dir == target_dir
    assert result.netlist_path == target_dir / "circuit.cir"


def test_run_xyce_netlist_supports_nested_csv_name_paths(monkeypatch, tmp_path):
    def _fake_run(args, cwd, capture_output, text):
        nested = Path(cwd) / "nested" / "output.csv"
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("TIME,V(N_1)\n0.0,1.0\n")
        nested.with_suffix(".prn").write_text("prn")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="nested/output.csv",
        keep_run_dir=True,
    )

    assert result.waveforms.shape == (1, 2)
    assert (result.run_dir / "nested" / "output.csv").exists()


def test_run_xyce_netlist_removes_artifacts_when_keep_run_dir_is_false(monkeypatch, tmp_path):
    def _fake_run(args, cwd, capture_output, text):
        csv_path = Path(cwd) / "nested" / "output.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("TIME,V(N_1)\n0.0,1.0\n")
        csv_path.with_suffix(".prn").write_text("prn")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="nested/output.csv",
        run_name="cleanup",
        keep_run_dir=False,
    )

    assert not result.netlist_path.exists()
    assert not (result.run_dir / "nested" / "output.csv").exists()
    assert not (result.run_dir / "nested" / "output.prn").exists()


def test_run_xyce_netlist_preserves_artifacts_when_keep_run_dir_is_true(monkeypatch, tmp_path):
    def _fake_run(args, cwd, capture_output, text):
        (Path(cwd) / "output.csv").write_text("TIME,V(N_1)\n0.0,1.0\n")
        (Path(cwd) / "output.prn").write_text("prn")
        return _completed_process()

    monkeypatch.setattr(engine.subprocess, "run", _fake_run)

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="keep",
        keep_run_dir=True,
    )

    assert result.netlist_path.exists()
    assert (result.run_dir / "output.csv").exists()
    assert (result.run_dir / "output.prn").exists()


def test_run_xyce_netlist_raises_xyce_run_error_with_full_context_on_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(
        engine.subprocess,
        "run",
        lambda *args, **kwargs: _completed_process(returncode=7, stdout="solver out", stderr="solver err"),
    )

    with pytest.raises(XyceRunError) as exc_info:
        run_xyce_netlist(
            xyce_path="Xyce",
            base_out_dir=tmp_path,
            netlist_content="* test\n.END\n",
            csv_name="output.csv",
            run_name="failure",
            keep_run_dir=True,
        )

    error = exc_info.value
    assert error.returncode == 7
    assert error.stdout == "solver out"
    assert error.stderr == "solver err"
    assert error.run_dir == tmp_path / "failure"
    assert error.netlist_path == tmp_path / "failure" / "circuit.cir"
    assert error.csv_path == tmp_path / "failure" / "output.csv"
    assert error.solve_time_sec is not None
    assert "solver out" in str(error)
    assert "solver err" in str(error)


def test_run_xyce_netlist_bubbles_file_not_found_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        engine.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("missing")),
    )

    with pytest.raises(FileNotFoundError, match="missing"):
        run_xyce_netlist(
            xyce_path="Xyce",
            base_out_dir=tmp_path,
            netlist_content="* test\n.END\n",
            csv_name="output.csv",
        )


def test_run_xyce_netlist_bubbles_permission_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        engine.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("denied")),
    )

    with pytest.raises(PermissionError, match="denied"):
        run_xyce_netlist(
            xyce_path="Xyce",
            base_out_dir=tmp_path,
            netlist_content="* test\n.END\n",
            csv_name="output.csv",
        )


def test_run_xyce_netlist_returns_empty_waveforms_when_csv_is_missing_after_success(monkeypatch, tmp_path):
    monkeypatch.setattr(engine.subprocess, "run", lambda *args, **kwargs: _completed_process())

    result = run_xyce_netlist(
        xyce_path="Xyce",
        base_out_dir=tmp_path,
        netlist_content="* test\n.END\n",
        csv_name="output.csv",
        run_name="missing_csv",
        keep_run_dir=True,
    )

    assert result.waveforms.empty
