from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

import xyce_py.graph as graph_module
from xyce_py.engine import XyceExecutionResult, find_xyce_executable
from xyce_py.graph import CircuitGraph
from xyce_py.models import Capacitor, Resistor, VoltageSource


def _xyce_available() -> bool:
    known_path = Path("/usr/local/XyceNF_7.10/bin/Xyce")
    return known_path.exists() or shutil.which("Xyce") is not None


@pytest.fixture
def xyce_path_or_skip() -> str:
    if not _xyce_available():
        pytest.skip("Xyce is not available in this environment.")
    return find_xyce_executable()


@pytest.fixture
def build_voltage_divider(tmp_path):
    def _build(*, xyce_path: str = "Xyce", base_out_dir: Path | None = None) -> CircuitGraph:
        graph = CircuitGraph(
            xyce_path=xyce_path,
            base_out_dir=str(base_out_dir or tmp_path),
        )
        graph.add_node("gnd", is_ground=True)
        graph.add_branch("vin", "gnd", [VoltageSource("src", 10.0)])
        graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
        graph.add_branch("vout", "gnd", [Resistor("r2", 1000)])
        return graph

    return _build


@pytest.fixture
def build_transient_graph(tmp_path):
    def _build(*, xyce_path: str = "Xyce", base_out_dir: Path | None = None) -> CircuitGraph:
        graph = CircuitGraph(
            xyce_path=xyce_path,
            base_out_dir=str(base_out_dir or tmp_path),
        )
        graph.add_node("gnd", is_ground=True)
        graph.add_branch(
            "vin",
            "gnd",
            [VoltageSource("pulse", 0.0, "PULSE(0 1 0 1u 1u 5u 10u)")],
        )
        graph.add_branch("vin", "vout", [Resistor("r1", 1000)])
        graph.add_branch("vout", "gnd", [Capacitor("c1", "1u")])
        return graph

    return _build


@pytest.fixture
def stub_xyce_execution(monkeypatch):
    calls: list[dict[str, object]] = []

    def _install(
        *,
        waveforms: pd.DataFrame | None = None,
        stdout: str = "solver stdout",
        stderr: str = "",
        solve_time_sec: float = 0.01,
    ) -> list[dict[str, object]]:
        frame = waveforms if waveforms is not None else pd.DataFrame({"V(N_1)": [10.0], "V(N_2)": [5.0]})

        def _fake_run_xyce_netlist(**kwargs):
            calls.append(kwargs)
            run_dir = Path(kwargs["base_out_dir"]) / kwargs["run_name"]
            return XyceExecutionResult(
                run_dir=run_dir,
                netlist_path=run_dir / "circuit.cir",
                stdout=stdout,
                stderr=stderr,
                waveforms=frame.copy(),
                solve_time_sec=solve_time_sec,
            )

        monkeypatch.setattr(graph_module, "run_xyce_netlist", _fake_run_xyce_netlist)
        return calls

    return _install
