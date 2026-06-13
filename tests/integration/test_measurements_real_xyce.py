from __future__ import annotations

import pytest

from xyce_py import MeasureDirective, OutputSpec, XyceProject


pytestmark = pytest.mark.xyce


def test_xyce_project_extracts_measurements_from_real_xyce_mt0_file(tmp_path, xyce_path_or_skip):
    project = XyceProject(
        "measurements",
        f"""* measurement extraction
V1 in 0 PULSE(0 1 0 1n 1n 5n 10n)
R1 in out 1k
C1 out 0 1n
.TRAN 1n 20n
.PRINT TRAN FORMAT=CSV FILE=waveforms.csv V(out)
{MeasureDirective("TRAN", "max_out", "MAX V(out)").to_spice()}
.END
""",
        output_specs=(
            OutputSpec.csv("waveforms", "waveforms.csv"),
            OutputSpec.text("measurements", "circuit.cir.mt0"),
        ),
    )

    result = project.run(xyce_path=xyce_path_or_skip, target_dir=tmp_path / "run")
    measurements = result.measurements()

    assert "MAX_OUT" in measurements
    assert measurements["MAX_OUT"].value is not None
    assert measurements["MAX_OUT"].value > 0.0
