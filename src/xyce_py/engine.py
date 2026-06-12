from __future__ import annotations

from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Optional
import subprocess
import time

import pandas as pd


def find_xyce_executable() -> str:
    default_xyce_path = "/usr/local/XyceNF_7.10/bin/Xyce"
    if Path(default_xyce_path).exists():
        return default_xyce_path
    return shutil.which("Xyce") or "Xyce"


def _read_waveforms(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


@dataclass(frozen=True)
class XyceExecutionResult:
    run_dir: Path
    netlist_path: Path
    stdout: str
    stderr: str
    waveforms: pd.DataFrame
    solve_time_sec: float


def execute_xyce_netlist(
    *,
    xyce_path: str,
    base_out_dir: Path | str,
    netlist_content: str,
    csv_name: str,
    run_name: str = "run",
    target_dir: Optional[Path] = None,
    keep_run_dir: bool = False,
) -> XyceExecutionResult:
    if target_dir:
        run_dir = Path(target_dir)
    else:
        base_path = Path(base_out_dir)
        if not base_path.is_absolute():
            base_path = base_path.resolve()
        run_dir = base_path / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    netlist_path = run_dir / "circuit.cir"
    netlist_path.write_text(netlist_content)
    csv_path = run_dir / csv_name
    if csv_path.parent != run_dir:
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    solve_started_at = time.perf_counter()
    completed_process = subprocess.run(
        [xyce_path, netlist_path.name],
        cwd=run_dir,
        capture_output=True,
        text=True,
    )
    solve_time_sec = time.perf_counter() - solve_started_at

    if completed_process.returncode != 0:
        error_message = (
            f"Xyce failed (code {completed_process.returncode}).\n\n"
            f"--- XYCE STDOUT (Detailed Error) ---\n{completed_process.stdout}\n"
            f"--- XYCE STDERR ---\n{completed_process.stderr}"
        )
        raise XyceRunError(
            error_message,
            returncode=completed_process.returncode,
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
            run_dir=run_dir,
            netlist_path=netlist_path,
            csv_path=csv_path,
            solve_time_sec=solve_time_sec,
        )

    waveforms = _read_waveforms(csv_path)

    if not keep_run_dir:
        artifact_paths = [netlist_path, csv_path, csv_path.with_suffix(".prn")]
        for artifact_path in artifact_paths:
            artifact_path.unlink(missing_ok=True)

    return XyceExecutionResult(
        run_dir,
        netlist_path,
        completed_process.stdout,
        completed_process.stderr,
        waveforms,
        solve_time_sec,
    )


class XyceRunError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        returncode: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        run_dir: Optional[Path] = None,
        netlist_path: Optional[Path] = None,
        csv_path: Optional[Path] = None,
        solve_time_sec: Optional[float] = None,
    ):
        super().__init__(message)
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.run_dir = run_dir
        self.netlist_path = netlist_path
        self.csv_path = csv_path
        self.solve_time_sec = solve_time_sec
