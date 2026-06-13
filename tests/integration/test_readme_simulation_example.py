from __future__ import annotations

import pytest

from tests.readme_helpers import extract_python_snippet


pytestmark = pytest.mark.xyce


def test_run_with_xyce_readme_snippet_executes(xyce_path_or_skip):
    namespace = {"__name__": "__main__"}

    exec(extract_python_snippet("Run with Xyce"), namespace)

    assert "result" in namespace
    assert len(namespace["result"].waveforms) == 1
