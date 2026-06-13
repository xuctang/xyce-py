from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tools.pip_audit_policy import build_ignore_args, load_allowlist, validate_allowlist


pytestmark = pytest.mark.unit


def _write_allowlist(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_pip_audit_policy_accepts_empty_allowlist(tmp_path):
    allowlist_path = _write_allowlist(tmp_path / "allowlist.json", [])

    entries = load_allowlist(allowlist_path)
    validate_allowlist(entries, today=date(2026, 4, 15))

    assert build_ignore_args(entries) == []


def test_pip_audit_policy_builds_ignore_args_for_valid_entry(tmp_path):
    allowlist_path = _write_allowlist(
        tmp_path / "allowlist.json",
        [
            {
                "id": "GHSA-1234",
                "package": "example",
                "reason": "Accepted until upstream fix ships",
                "owner": "release",
                "expires_on": "2026-12-31",
            }
        ],
    )

    entries = load_allowlist(allowlist_path)
    validate_allowlist(entries, today=date(2026, 4, 15))

    assert build_ignore_args(entries) == ["--ignore-vuln", "GHSA-1234"]


def test_pip_audit_policy_rejects_expired_exception(tmp_path):
    allowlist_path = _write_allowlist(
        tmp_path / "allowlist.json",
        [
            {
                "id": "GHSA-expired",
                "package": "example",
                "reason": "Temporary exception",
                "owner": "release",
                "expires_on": "2026-01-01",
            }
        ],
    )

    entries = load_allowlist(allowlist_path)

    with pytest.raises(SystemExit, match="expired entries"):
        validate_allowlist(entries, today=date(2026, 4, 15))


def test_pip_audit_policy_rejects_malformed_entries(tmp_path):
    allowlist_path = _write_allowlist(
        tmp_path / "allowlist.json",
        [{"id": "GHSA-bad", "package": "example"}],
    )

    with pytest.raises(SystemExit, match="missing required fields"):
        load_allowlist(allowlist_path)
