from __future__ import annotations

import json
import subprocess
import sys

import pytest


pytestmark = pytest.mark.xyce


def test_cli_run_executes_raw_netlist_with_real_xyce(tmp_path, xyce_path_or_skip):
    netlist_path = tmp_path / "divider.cir"
    netlist_path.write_text(
        """* cli raw voltage divider
V1 1 0 DC 10
R1 1 2 1000
R2 2 0 1000
.OP
.PRINT DC FORMAT=CSV FILE=cli.csv V(1) V(2)
.END
"""
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "xyce_py",
            "run",
            str(netlist_path),
            "--xyce-path",
            xyce_path_or_skip,
            "--target-dir",
            str(tmp_path / "run"),
            "--csv-output",
            "waveforms",
            "cli.csv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)

    assert payload["project"] == "divider"
    assert payload["run_dir"] == str(tmp_path / "run")
    assert payload["outputs"]["waveforms"]["exists"] is True
    assert payload["outputs"]["waveforms"]["rows"] == 1
    assert payload["outputs"]["waveforms"]["columns"] == ["V(1)", "V(2)"]
