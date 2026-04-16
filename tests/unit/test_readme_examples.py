from __future__ import annotations

import pytest

from tests.readme_helpers import extract_python_snippet


pytestmark = pytest.mark.unit


def test_compile_only_quick_start_readme_snippet_executes():
    namespace = {"__name__": "__main__"}

    exec(extract_python_snippet("Quick Start"), namespace)

    assert "netlist" in namespace
    assert namespace["netlist"].startswith("* Generated Circuit\n")
    assert namespace["netlist"].endswith(".END\n")
