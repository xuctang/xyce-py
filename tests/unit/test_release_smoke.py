from __future__ import annotations

import importlib.metadata as metadata
import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


SCRIPT_PATH = Path("tools/release_smoke.py")


def test_release_smoke_script_succeeds_for_installed_package():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert payload["package_name"] == "xyce-py"
    assert payload["package_version"] == metadata.version("xyce-py")
    assert payload["required_python"] == ">=3.10"
    assert payload["netlist_line_count"] > 0


def test_release_smoke_script_rejects_mismatched_expected_version():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--expect-version", "9.9.9"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "did not match expected version" in result.stderr
