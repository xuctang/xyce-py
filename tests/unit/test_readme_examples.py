from __future__ import annotations

import pytest

from tests.readme_helpers import README_PATH, extract_python_snippet


pytestmark = pytest.mark.unit


def test_compile_only_quick_start_readme_snippet_executes():
    namespace = {"__name__": "__main__"}

    exec(extract_python_snippet("Quick Start"), namespace)

    assert "netlist" in namespace
    assert namespace["netlist"].startswith("* Generated Circuit\n")
    assert namespace["netlist"].endswith(".END\n")


def test_readme_guides_zero_prep_xyce_setup():
    readme = README_PATH.read_text(encoding="utf-8")

    assert "## Configure Xyce" in readme
    assert "https://xyce.sandia.gov/downloads/executables/" in readme
    assert "Xyce -v" in readme
    assert "find_xyce_executable" in readme
    assert 'xyce_path="/path/to/Xyce"' in readme
    assert "## Troubleshooting Setup" in readme
