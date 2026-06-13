from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.release_helpers import (
    find_site_packages_path,
    require_final,
    require_prerelease,
    select_previous_final_version,
)


pytestmark = pytest.mark.unit


def test_require_final_accepts_final_versions():
    require_final("1.2.3")


def test_require_final_rejects_prerelease_versions():
    with pytest.raises(SystemExit, match="not a final release"):
        require_final("1.2.3rc1")


def test_require_prerelease_accepts_release_candidate_versions():
    require_prerelease("1.2.3rc2")


def test_require_prerelease_rejects_final_versions():
    with pytest.raises(SystemExit, match="not a release candidate"):
        require_prerelease("1.2.3")


def test_site_packages_path_matches_target_python_runtime():
    expected = (
        subprocess.run(
            [sys.executable, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
    )

    assert find_site_packages_path(Path(sys.executable)) == expected


def test_select_previous_final_version_ignores_prereleases():
    versions = ["0.9.9", "1.0.0rc1", "1.0.0", "1.0.1rc1", "1.0.1", "1.0.2rc1"]

    assert select_previous_final_version("1.0.2", versions) == "1.0.1"


def test_select_previous_final_version_raises_when_no_older_final_exists():
    with pytest.raises(SystemExit, match="No previous final release exists"):
        select_previous_final_version("1.0.0", ["1.0.0rc1", "1.0.0"])
