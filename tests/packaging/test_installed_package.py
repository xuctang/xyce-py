from __future__ import annotations

import importlib.metadata as metadata
import tarfile
import zipfile
from pathlib import Path

import pytest

import xyce_py
from tests.readme_helpers import extract_python_snippet


pytestmark = pytest.mark.packaging


def test_installed_wheel_imports_xyce_py_and_top_level_exports():
    assert xyce_py.CircuitGraph is not None
    assert xyce_py.Resistor is not None
    assert "CircuitGraph" in xyce_py.__all__
    assert "find_xyce_executable" in xyce_py.__all__


def test_installed_wheel_exposes_expected_distribution_metadata():
    package_metadata = metadata.metadata("xyce-py")

    assert package_metadata["Name"] == "xyce-py"
    assert metadata.version("xyce-py")
    assert package_metadata["Summary"]
    assert package_metadata["Requires-Python"] == ">=3.10"
    assert package_metadata["License-Expression"] == "MIT"
    assert package_metadata.get_all("Project-URL") == [
        "Repository, https://github.com/xuctang/xyce-py",
        "Issues, https://github.com/xuctang/xyce-py/issues",
        "Documentation, https://github.com/xuctang/xyce-py#readme",
    ]


def test_built_sdist_and_wheel_contain_required_package_files():
    dist_dir = Path("dist")
    if not any(dist_dir.glob("*.whl")) or not any(dist_dir.glob("*.tar.gz")):
        pytest.skip("Built artifacts are not present; run `python -m build` first.")
    wheel_path = next(dist_dir.glob("*.whl"))
    sdist_path = next(dist_dir.glob("*.tar.gz"))
    required_package_sources = [
        Path("src/xyce_py/__init__.py"),
        Path("src/xyce_py/compiler.py"),
        Path("src/xyce_py/engine.py"),
        Path("src/xyce_py/graph.py"),
        Path("src/xyce_py/models.py"),
        Path("src/xyce_py/netlists.py"),
        Path("src/xyce_py/outputs.py"),
    ]
    latest_source_mtime = max(path.stat().st_mtime for path in required_package_sources)
    if min(wheel_path.stat().st_mtime, sdist_path.stat().st_mtime) < latest_source_mtime:
        pytest.skip("Built artifacts are stale; run `python -m build` first.")

    with zipfile.ZipFile(wheel_path) as wheel_archive:
        wheel_names = set(wheel_archive.namelist())

    with tarfile.open(sdist_path, "r:gz") as sdist_archive:
        sdist_names = set(sdist_archive.getnames())

    assert "xyce_py/__init__.py" in wheel_names
    assert "xyce_py/compiler.py" in wheel_names
    assert "xyce_py/engine.py" in wheel_names
    assert "xyce_py/graph.py" in wheel_names
    assert "xyce_py/models.py" in wheel_names
    assert "xyce_py/netlists.py" in wheel_names
    assert "xyce_py/outputs.py" in wheel_names

    sdist_root = next(name for name in sdist_names if name.endswith("/pyproject.toml")).rsplit("/", 1)[0]
    assert f"{sdist_root}/README.md" in sdist_names
    assert f"{sdist_root}/LICENSE" in sdist_names
    assert f"{sdist_root}/src/xyce_py/__init__.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/compiler.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/engine.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/graph.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/models.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/netlists.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/outputs.py" in sdist_names


def test_installed_wheel_executes_compile_only_quick_start_snippet():
    namespace = {"__name__": "__main__"}

    exec(extract_python_snippet("Quick Start"), namespace)

    assert "netlist" in namespace
    assert namespace["netlist"].startswith("* Generated Circuit\n")
    assert namespace["netlist"].endswith(".END\n")
