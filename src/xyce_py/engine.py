from __future__ import annotations
from dataclasses import dataclass
import shutil
from pathlib import Path
from typing import Optional
import subprocess
import time

import pandas as pd


def find_xyce_executable() -> str:
    known_path = "/usr/local/XyceNF_7.10/bin/Xyce"
    if Path(known_path).exists():
        return known_path
    return shutil.which("Xyce") or "Xyce"


def _read_waveforms(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        return pd.read_csv(csv_path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


@dataclass
class _XyceExecutionResult:
    run_dir: Path
    netlist_path: Path
    stdout: str
    stderr: str
    waveforms: pd.DataFrame
    solve_time_sec: float


def _execute_xyce_netlist(
    *,
    xyce_path: str,
    base_out_dir: Path | str,
    netlist_content: str,
    csv_name: str,
    run_name: str = "run",
    target_dir: Optional[Path] = None,
    keep_run_dir: bool = False,
) -> _XyceExecutionResult:
    if target_dir:
        run_dir = Path(target_dir)
    else:
        run_dir = Path(base_out_dir).resolve() / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    netlist_path = run_dir / "circuit.cir"
    netlist_path.write_text(netlist_content)
    csv_path = run_dir / csv_name
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    solve_start = time.perf_counter()
    p = subprocess.run(
        [xyce_path, netlist_path.name],
        cwd=run_dir,
        capture_output=True,
        text=True,
    )
    solve_time_sec = time.perf_counter() - solve_start

    if p.returncode != 0:
        error_msg = (
            f"Xyce failed (code {p.returncode}).\n\n"
            f"--- XYCE STDOUT (Detailed Error) ---\n{p.stdout}\n"
            f"--- XYCE STDERR ---\n{p.stderr}"
        )
        raise XyceRunError(
            error_msg,
            returncode=p.returncode,
            stdout=p.stdout,
            stderr=p.stderr,
            run_dir=run_dir,
            netlist_path=netlist_path,
            csv_path=csv_path,
            solve_time_sec=solve_time_sec,
        )

    waveforms = _read_waveforms(csv_path)

    if not keep_run_dir:
        artifacts = [netlist_path, csv_path, csv_path.with_suffix(".prn")]
        for file_to_rem in artifacts:
            if file_to_rem.exists():
                file_to_rem.unlink()

    return _XyceExecutionResult(run_dir, netlist_path, p.stdout, p.stderr, waveforms, solve_time_sec)

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
