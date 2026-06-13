from __future__ import annotations

import pytest

from xyce_py import OutputSpec, SweepParameter, XyceParameterSweep


pytestmark = pytest.mark.xyce


def test_parameter_sweep_runs_parametric_raw_netlist_with_real_xyce(tmp_path, xyce_path_or_skip):
    sweep = XyceParameterSweep(
        "divider-sweep",
        """* sweep divider
V1 1 0 DC 10
R1 1 2 {RLOAD}
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=out.csv V(2)
.END
""",
        parameters=(SweepParameter("RLOAD", [1000, 3000]),),
        output_specs=(OutputSpec.csv("waveforms", "out.csv"),),
    )

    result = sweep.run(xyce_path=xyce_path_or_skip, base_out_dir=tmp_path)
    first_vout = result.run(0).result.output("waveforms").frame.iloc[0]["V(2)"]
    second_vout = result.run(1).result.output("waveforms").frame.iloc[0]["V(2)"]

    assert first_vout == pytest.approx(5.0, abs=1e-3)
    assert second_vout == pytest.approx(2.5, abs=1e-3)
