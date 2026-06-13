from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


FINAL_VERSION_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
PRERELEASE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+rc\d+$")
VERSION_LINE_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)
PACKAGE_INDEX_URLS = {
    "pypi": "https://pypi.org/pypi/{package_name}/json",
    "testpypi": "https://test.pypi.org/pypi/{package_name}/json",
}


def read_version(pyproject_path: Path) -> str:
    pyproject_text = pyproject_path.read_text(encoding="utf-8")
    match = VERSION_LINE_RE.search(pyproject_text)
    if match is None:
        raise SystemExit(f"Could not find a project version in {pyproject_path}.")
    return match.group(1)


def require_final(version: str) -> None:
    if not FINAL_VERSION_RE.fullmatch(version):
        raise SystemExit(
            f"Version {version!r} is not a final release. "
            "Expected a version like 1.0.1 before publishing to PyPI."
        )


def require_prerelease(version: str) -> None:
    if not PRERELEASE_VERSION_RE.fullmatch(version):
        raise SystemExit(
            f"Version {version!r} is not a release candidate. "
            "Expected a version like 1.0.1rc1 before publishing to TestPyPI."
        )


def parse_final_version(version: str) -> tuple[int, int, int]:
    match = FINAL_VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"{version!r} is not a final semantic version.")
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch"))


def select_previous_final_version(current_version: str, versions: list[str]) -> str:
    current_version_parts = parse_final_version(current_version)
    previous_final_candidates = []
    for version in versions:
        if not FINAL_VERSION_RE.fullmatch(version):
            continue
        version_parts = parse_final_version(version)
        if version_parts < current_version_parts:
            previous_final_candidates.append((version_parts, version))
    if not previous_final_candidates:
        raise SystemExit(f"No previous final release exists before {current_version!r}.")
    return max(previous_final_candidates)[1]


def fetch_release_versions(package_name: str, index: str) -> list[str]:
    if index not in PACKAGE_INDEX_URLS:
        raise SystemExit(f"Unsupported package index {index!r}. Use one of: {', '.join(PACKAGE_INDEX_URLS)}.")
    url = PACKAGE_INDEX_URLS[index].format(package_name=package_name)
    try:
        with urlopen(url, timeout=30) as response:
            metadata_payload = json.load(response)
    except HTTPError as exc:
        raise SystemExit(f"Failed to fetch release metadata from {url}: HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SystemExit(f"Failed to fetch release metadata from {url}: {exc.reason}.") from exc
    release_map = metadata_payload.get("releases")
    if not isinstance(release_map, dict):
        raise SystemExit(f"Release metadata from {url} did not contain a 'releases' mapping.")
    return sorted(release_map)


def find_dist_path(dist_dir: Path, pattern: str) -> Path:
    artifact_paths = sorted(dist_dir.glob(pattern))
    if len(artifact_paths) != 1:
        raise SystemExit(
            f"Expected exactly one artifact matching {pattern!r} in {dist_dir}, found {len(artifact_paths)}."
        )
    return artifact_paths[0]


def find_site_packages_path(python_executable: Path) -> str:
    completed_process = subprocess.run(
        [
            str(python_executable),
            "-c",
            "import sysconfig; print(sysconfig.get_path('purelib'))",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed_process.stdout.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Release workflow helpers for xyce-py.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("version", "require-final", "require-prerelease"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--pyproject",
            type=Path,
            default=Path("pyproject.toml"),
            help="Path to pyproject.toml.",
        )

    for command, pattern in (("wheel-path", "*.whl"), ("sdist-path", "*.tar.gz")):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--dist-dir",
            type=Path,
            default=Path("dist"),
            help="Directory containing built distributions.",
        )
        command_parser.set_defaults(pattern=pattern)

    command_parser = subparsers.add_parser("site-packages-path")
    command_parser.add_argument(
        "--python-executable",
        type=Path,
        default=Path(sys.executable),
        help="Python executable inside the virtual environment to inspect.",
    )

    command_parser = subparsers.add_parser("previous-final-version")
    command_parser.add_argument(
        "--current-version",
        required=True,
        help="Current target release version; must be a final release version.",
    )
    command_parser.add_argument(
        "--package-name",
        default="xyce-py",
        help="Package name to inspect on the package index.",
    )
    command_parser.add_argument(
        "--index",
        default="pypi",
        choices=sorted(PACKAGE_INDEX_URLS),
        help="Package index to inspect for previous releases.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print(read_version(args.pyproject))
        return 0

    if args.command == "require-final":
        version = read_version(args.pyproject)
        require_final(version)
        print(version)
        return 0

    if args.command == "require-prerelease":
        version = read_version(args.pyproject)
        require_prerelease(version)
        print(version)
        return 0

    if args.command == "wheel-path":
        print(find_dist_path(args.dist_dir, args.pattern))
        return 0

    if args.command == "sdist-path":
        print(find_dist_path(args.dist_dir, args.pattern))
        return 0

    if args.command == "site-packages-path":
        print(find_site_packages_path(args.python_executable))
        return 0

    if args.command == "previous-final-version":
        require_final(args.current_version)
        versions = fetch_release_versions(args.package_name, args.index)
        print(select_previous_final_version(args.current_version, versions))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
