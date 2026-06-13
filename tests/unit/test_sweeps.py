from __future__ import annotations

from pathlib import Path
import random

import pandas as pd
import pytest

import xyce_py.sweeps as sweeps
from xyce_py.engine import XyceExecutionResult
from xyce_py.netlists import XyceProjectResult
from xyce_py.outputs import OutputSpec
from xyce_py.sweeps import (
    MonteCarloParameter,
    NormalDistribution,
    SweepParameter,
    SweepPoint,
    UniformDistribution,
    XyceMonteCarloSweep,
    XyceParameterSweep,
    XyceParameterSweepResult,
)


pytestmark = pytest.mark.unit


RAW_NETLIST = """* sweep divider
V1 1 0 DC 10
R1 1 2 {RLOAD}
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=out.csv V(2)
.END
"""


def _fake_project_result(run_dir: Path) -> XyceProjectResult:
    execution = XyceExecutionResult(
        run_dir=run_dir,
        netlist_path=run_dir / "circuit.cir",
        stdout="solver stdout",
        stderr="",
        waveforms=pd.DataFrame({"V(2)": [5.0]}),
        solve_time_sec=0.01,
    )
    return XyceProjectResult(execution=execution, outputs={})


def test_sweep_parameter_formats_values_through_param_directive_contract():
    parameter = SweepParameter("RLOAD", [1000, "2k"])

    assert parameter.name == "RLOAD"
    assert parameter.values == ("1000.0", "2k")


@pytest.mark.parametrize("bad_values", [[], (), "1k", [True], [None], [""]])
def test_sweep_parameter_rejects_invalid_values(bad_values):
    with pytest.raises((TypeError, ValueError)):
        SweepParameter("RLOAD", bad_values)


def test_monte_carlo_distributions_validate_numeric_contracts():
    assert UniformDistribution(1, 2).sample(random.Random(0)) > 1
    assert isinstance(NormalDistribution(0, 1).sample(random.Random(0)), float)

    with pytest.raises(ValueError, match="high must be greater than low"):
        UniformDistribution(1, 1)
    with pytest.raises(ValueError, match="stddev must be positive"):
        NormalDistribution(0, 0)
    with pytest.raises(TypeError, match="distribution must be"):
        MonteCarloParameter("RLOAD", object())


def test_xyce_parameter_sweep_builds_cartesian_sweep_points_and_netlists():
    sweep = XyceParameterSweep(
        "divider",
        RAW_NETLIST,
        (
            SweepParameter("RLOAD", [1000, 3000]),
            SweepParameter("CLOAD", ["1n", "2n"]),
        ),
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )

    points = sweep.points()
    first_netlist = sweep.netlist_for_point(points[0])

    assert [dict(point.parameters) for point in points] == [
        {"RLOAD": "1000.0", "CLOAD": "1n"},
        {"RLOAD": "1000.0", "CLOAD": "2n"},
        {"RLOAD": "3000.0", "CLOAD": "1n"},
        {"RLOAD": "3000.0", "CLOAD": "2n"},
    ]
    assert first_netlist.startswith("* sweep divider\n.PARAM RLOAD=1000.0\n.PARAM CLOAD=1n\n")
    assert first_netlist.endswith(".END\n")


def test_xyce_monte_carlo_sweep_generates_deterministic_points_and_netlists():
    first = XyceMonteCarloSweep(
        "mc",
        RAW_NETLIST,
        parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1000, 3000)),),
        samples=3,
        seed=42,
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )
    second = XyceMonteCarloSweep(
        "mc",
        RAW_NETLIST,
        parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1000, 3000)),),
        samples=3,
        seed=42,
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )

    first_points = first.points()
    second_points = second.points()

    assert [dict(point.parameters) for point in first_points] == [
        dict(point.parameters) for point in second_points
    ]
    assert len(first_points) == 3
    assert first.netlist_for_point(first_points[0]).startswith("* sweep divider\n.PARAM RLOAD=")


def test_xyce_parameter_sweep_rejects_duplicate_or_existing_param_names():
    with pytest.raises(ValueError, match="Duplicate sweep parameter name"):
        XyceParameterSweep(
            "bad",
            RAW_NETLIST,
            (SweepParameter("RLOAD", [1000]), SweepParameter("rload", [2000])),
        )

    with pytest.raises(ValueError, match="already be defined"):
        XyceParameterSweep(
            "bad",
            "* sweep divider\n.PARAM RLOAD=1k\nR1 1 0 {RLOAD}\n.OP\n.END\n",
            (SweepParameter("RLOAD", [1000]),),
        )


def test_xyce_monte_carlo_sweep_rejects_invalid_contracts():
    with pytest.raises(ValueError, match="samples must be positive"):
        XyceMonteCarloSweep(
            "bad",
            RAW_NETLIST,
            parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1, 2)),),
            samples=0,
        )
    with pytest.raises(TypeError, match="seed must be an integer"):
        XyceMonteCarloSweep(
            "bad",
            RAW_NETLIST,
            parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1, 2)),),
            samples=1,
            seed=True,
        )
    with pytest.raises(ValueError, match="Duplicate Monte Carlo parameter"):
        XyceMonteCarloSweep(
            "bad",
            RAW_NETLIST,
            parameters=(
                MonteCarloParameter("RLOAD", UniformDistribution(1, 2)),
                MonteCarloParameter("rload", NormalDistribution(1, 0.1)),
            ),
            samples=1,
        )
    with pytest.raises(ValueError, match="already be defined"):
        XyceMonteCarloSweep(
            "bad",
            "* sweep divider\n.PARAM RLOAD=1k\nR1 1 0 {RLOAD}\n.OP\n.END\n",
            parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1, 2)),),
            samples=1,
        )


def test_xyce_parameter_sweep_rejects_invalid_contracts():
    with pytest.raises(ValueError, match="parameters must be a non-empty sequence"):
        XyceParameterSweep("bad", RAW_NETLIST, ())

    with pytest.raises(TypeError, match="parameters must contain only SweepParameter"):
        XyceParameterSweep("bad", RAW_NETLIST, ("RLOAD",))

    with pytest.raises(TypeError, match="point must be a SweepPoint"):
        XyceParameterSweep("bad", RAW_NETLIST, (SweepParameter("RLOAD", [1000]),)).netlist_for_point(object())


def test_xyce_parameter_sweep_from_file_reads_exact_netlist_content(tmp_path):
    netlist_path = tmp_path / "divider.cir"
    netlist_path.write_text(RAW_NETLIST)

    sweep = XyceParameterSweep.from_file(
        netlist_path,
        name="from-file",
        parameters=(SweepParameter("RLOAD", [1000]),),
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )

    assert sweep.name == "from-file"
    assert sweep.netlist_content == RAW_NETLIST
    assert sweep.output_specs == (OutputSpec.csv("waveforms", "out.csv"),)


def test_xyce_parameter_sweep_run_executes_each_point_through_xyce_project(monkeypatch, tmp_path):
    created_projects: list[dict[str, object]] = []

    class FakeProject:
        def __init__(self, name, netlist_content, output_specs=()):
            self.name = name
            self.netlist_content = netlist_content
            self.output_specs = tuple(output_specs)
            created_projects.append(
                {
                    "name": name,
                    "netlist_content": netlist_content,
                    "output_specs": tuple(output_specs),
                }
            )

        def run(self, **kwargs):
            return _fake_project_result(Path(kwargs["base_out_dir"]) / kwargs["run_name"])

    sweep = XyceParameterSweep(
        "divider",
        RAW_NETLIST,
        (SweepParameter("RLOAD", [1000, 3000]),),
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )
    monkeypatch.setattr(sweeps, "XyceProject", FakeProject)

    result = sweep.run(
        xyce_path="/opt/Xyce",
        base_out_dir=tmp_path,
        run_name="batch",
        keep_run_dirs=False,
    )

    assert [project["name"] for project in created_projects] == ["batch_0000", "batch_0001"]
    assert ".PARAM RLOAD=1000.0" in created_projects[0]["netlist_content"]
    assert ".PARAM RLOAD=3000.0" in created_projects[1]["netlist_content"]
    assert created_projects[0]["output_specs"] == (OutputSpec.csv("waveforms", "out.csv"),)
    assert [run.point.index for run in result.runs] == [0, 1]
    assert result.run(1).point.parameters["RLOAD"] == "3000.0"
    with pytest.raises(KeyError):
        result.run(3)


def test_xyce_monte_carlo_sweep_run_executes_generated_points_through_xyce_project(monkeypatch, tmp_path):
    created_projects: list[dict[str, object]] = []

    class FakeProject:
        def __init__(self, name, netlist_content, output_specs=()):
            created_projects.append(
                {
                    "name": name,
                    "netlist_content": netlist_content,
                    "output_specs": tuple(output_specs),
                }
            )

        def run(self, **kwargs):
            return _fake_project_result(Path(kwargs["base_out_dir"]) / kwargs["run_name"])

    sweep = XyceMonteCarloSweep(
        "mc",
        RAW_NETLIST,
        parameters=(MonteCarloParameter("RLOAD", UniformDistribution(1000, 3000)),),
        samples=2,
        seed=7,
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )
    monkeypatch.setattr(sweeps, "XyceProject", FakeProject)

    result = sweep.run(base_out_dir=tmp_path, run_name="mc-run")

    assert [project["name"] for project in created_projects] == ["mc-run_0000", "mc-run_0001"]
    assert all(".PARAM RLOAD=" in project["netlist_content"] for project in created_projects)
    assert [run.point.index for run in result.runs] == [0, 1]


def test_xyce_parameter_sweep_run_rejects_invalid_run_controls(tmp_path):
    sweep = XyceParameterSweep("divider", RAW_NETLIST, (SweepParameter("RLOAD", [1000]),))

    with pytest.raises(ValueError, match="run_name must be a non-empty string"):
        sweep.run(base_out_dir=tmp_path, run_name=" ")

    with pytest.raises(TypeError, match="keep_run_dirs must be a boolean"):
        sweep.run(base_out_dir=tmp_path, keep_run_dirs="yes")


def test_sweep_point_rejects_invalid_shape():
    with pytest.raises(ValueError, match="index must be non-negative"):
        SweepPoint(-1, {"RLOAD": "1k"})

    with pytest.raises(ValueError, match="parameters must be a non-empty mapping"):
        SweepPoint(0, {})


def test_sweep_point_parameters_are_read_only():
    point = SweepPoint(0, {"RLOAD": "1k"})

    with pytest.raises(TypeError):
        point.parameters["RLOAD"] = "2k"


def test_xyce_parameter_sweep_result_rejects_empty_runs():
    with pytest.raises(ValueError, match="runs must be a non-empty sequence"):
        XyceParameterSweepResult("empty", ())
