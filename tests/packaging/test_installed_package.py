from __future__ import annotations

import importlib.metadata as metadata
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

import xyce_py
import xyce_py.cli
from tests.readme_helpers import extract_python_snippet


pytestmark = pytest.mark.packaging


def test_installed_wheel_imports_xyce_py_and_top_level_exports():
    assert xyce_py.CircuitGraph is not None
    assert xyce_py.Resistor is not None
    assert xyce_py.cli.main is not None
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


def test_pyproject_declares_console_script_entry_point():
    if sys.version_info < (3, 11):
        pytest.skip("tomllib is available in the standard library on Python 3.11+.")
    import tomllib

    project_metadata = tomllib.loads(Path("pyproject.toml").read_text())

    assert project_metadata["project"]["scripts"]["xyce-py"] == "xyce_py.cli:main"


def test_built_sdist_and_wheel_contain_required_package_files():
    dist_dir = Path("dist")
    if not any(dist_dir.glob("*.whl")) or not any(dist_dir.glob("*.tar.gz")):
        pytest.skip("Built artifacts are not present; run `python -m build` first.")
    wheel_path = next(dist_dir.glob("*.whl"))
    sdist_path = next(dist_dir.glob("*.tar.gz"))
    required_package_sources = [
        Path("src/xyce_py/__init__.py"),
        Path("src/xyce_py/__main__.py"),
        Path("src/xyce_py/cli.py"),
        Path("src/xyce_py/compiler.py"),
        Path("src/xyce_py/directives.py"),
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
        entry_points_text = next(
            wheel_archive.read(name).decode()
            for name in wheel_names
            if name.endswith(".dist-info/entry_points.txt")
        )

    with tarfile.open(sdist_path, "r:gz") as sdist_archive:
        sdist_names = set(sdist_archive.getnames())

    assert "xyce_py/__init__.py" in wheel_names
    assert "xyce_py/__main__.py" in wheel_names
    assert "xyce_py/cli.py" in wheel_names
    assert "xyce_py/compiler.py" in wheel_names
    assert "xyce_py/directives.py" in wheel_names
    assert "xyce_py/engine.py" in wheel_names
    assert "xyce_py/graph.py" in wheel_names
    assert "xyce_py/models.py" in wheel_names
    assert "xyce_py/netlists.py" in wheel_names
    assert "xyce_py/outputs.py" in wheel_names
    assert "[console_scripts]" in entry_points_text
    assert "xyce-py = xyce_py.cli:main" in entry_points_text

    sdist_root = next(name for name in sdist_names if name.endswith("/pyproject.toml")).rsplit("/", 1)[0]
    assert f"{sdist_root}/README.md" in sdist_names
    assert f"{sdist_root}/LICENSE" in sdist_names
    assert f"{sdist_root}/src/xyce_py/__init__.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/__main__.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/cli.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/compiler.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/directives.py" in sdist_names
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
