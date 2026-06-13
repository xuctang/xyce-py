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


def _built_artifact_paths() -> tuple[Path, Path]:
    dist_dir = Path("dist")
    wheel_paths = sorted(dist_dir.glob("xyce_py-*.whl"))
    sdist_paths = sorted(dist_dir.glob("xyce_py-*.tar.gz"))
    if not wheel_paths or not sdist_paths:
        pytest.skip("Built artifacts are not present; run `python -m build` first.")
    assert len(wheel_paths) == 1
    assert len(sdist_paths) == 1
    return wheel_paths[0], sdist_paths[0]


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
    wheel_path, sdist_path = _built_artifact_paths()
    required_package_sources = [
        Path("src/xyce_py/__init__.py"),
        Path("src/xyce_py/__main__.py"),
        Path("src/xyce_py/_solutions.py"),
        Path("src/xyce_py/cli.py"),
        Path("src/xyce_py/compiler.py"),
        Path("src/xyce_py/directives.py"),
        Path("src/xyce_py/engine.py"),
        Path("src/xyce_py/features.py"),
        Path("src/xyce_py/graph.py"),
        Path("src/xyce_py/measurements.py"),
        Path("src/xyce_py/models.py"),
        Path("src/xyce_py/netlists.py"),
        Path("src/xyce_py/outputs.py"),
        Path("src/xyce_py/py.typed"),
        Path("src/xyce_py/sweeps.py"),
        Path("src/xyce_py/xdm.py"),
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
    assert "xyce_py/_solutions.py" in wheel_names
    assert "xyce_py/cli.py" in wheel_names
    assert "xyce_py/compiler.py" in wheel_names
    assert "xyce_py/directives.py" in wheel_names
    assert "xyce_py/engine.py" in wheel_names
    assert "xyce_py/features.py" in wheel_names
    assert "xyce_py/graph.py" in wheel_names
    assert "xyce_py/measurements.py" in wheel_names
    assert "xyce_py/models.py" in wheel_names
    assert "xyce_py/netlists.py" in wheel_names
    assert "xyce_py/outputs.py" in wheel_names
    assert "xyce_py/py.typed" in wheel_names
    assert "xyce_py/sweeps.py" in wheel_names
    assert "xyce_py/xdm.py" in wheel_names
    assert "[console_scripts]" in entry_points_text
    assert "xyce-py = xyce_py.cli:main" in entry_points_text

    sdist_root = next(name for name in sdist_names if name.endswith("/pyproject.toml")).rsplit("/", 1)[0]
    assert f"{sdist_root}/README.md" in sdist_names
    assert f"{sdist_root}/LICENSE" in sdist_names
    assert f"{sdist_root}/src/xyce_py/__init__.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/__main__.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/_solutions.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/cli.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/compiler.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/directives.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/engine.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/features.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/graph.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/measurements.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/models.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/netlists.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/outputs.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/py.typed" in sdist_names
    assert f"{sdist_root}/src/xyce_py/sweeps.py" in sdist_names
    assert f"{sdist_root}/src/xyce_py/xdm.py" in sdist_names


def test_built_sdist_includes_public_source_material_without_bloating_wheel():
    wheel_path, sdist_path = _built_artifact_paths()
    manifest_path = Path("MANIFEST.in")
    if min(wheel_path.stat().st_mtime, sdist_path.stat().st_mtime) < manifest_path.stat().st_mtime:
        pytest.skip("Built artifacts are stale; run `python -m build` first.")

    with zipfile.ZipFile(wheel_path) as wheel_archive:
        wheel_names = set(wheel_archive.namelist())

    with tarfile.open(sdist_path, "r:gz") as sdist_archive:
        sdist_names = set(sdist_archive.getnames())

    sdist_root = next(name for name in sdist_names if name.endswith("/pyproject.toml")).rsplit("/", 1)[0]
    required_sdist_files = {
        "CHANGELOG.md",
        "CONTEXT.md",
        "MANIFEST.in",
        "pytest.ini",
        "requirements.txt",
        "SECURITY.md",
        "constraints/runtime-min.txt",
        "docs/api-reference.md",
        "docs/capability-matrix.md",
        "docs/adr/0016-graph-input-and-result-projection.md",
        "examples/README.md",
        "examples/01_circuitgraph_quickstart.ipynb",
        "security/pip_audit_allowlist.json",
        "tests/conftest.py",
        "tests/readme_helpers.py",
        "tests/unit/test_examples.py",
        "tests/packaging/test_installed_package.py",
        "tools/release_smoke.py",
        "tools/pip_audit_policy.py",
        "tools/cleanroom/Dockerfile",
        "tools/cleanroom/run_registry_smoke.sh",
    }

    for relative_path in required_sdist_files:
        assert f"{sdist_root}/{relative_path}" in sdist_names

    wheel_prefixes_to_keep_out = (
        "constraints/",
        "docs/",
        "examples/",
        "security/",
        "tests/",
        "tools/",
    )
    assert not any(name.startswith(wheel_prefixes_to_keep_out) for name in wheel_names)
    assert "CONTEXT.md" not in wheel_names
    assert "pytest.ini" not in wheel_names
    assert "requirements.txt" not in wheel_names

    generated_path_markers = (
        "/.github/",
        "/.hypothesis/",
        "/.pkg-venv/",
        "/.pytest_cache/",
        "/.venv/",
        "/_xyce_runs/",
        "/build/",
        "/dist/",
        "/__pycache__/",
    )
    assert not any(any(marker in name for marker in generated_path_markers) for name in sdist_names)
    assert not any(name.endswith((".coverage", ".pyc", ".pyo", ".DS_Store")) for name in sdist_names)


def test_installed_wheel_executes_compile_only_quick_start_snippet():
    namespace = {"__name__": "__main__"}

    exec(extract_python_snippet("Quick Start"), namespace)

    assert "netlist" in namespace
    assert namespace["netlist"].startswith("* Generated Circuit\n")
    assert namespace["netlist"].endswith(".END\n")
