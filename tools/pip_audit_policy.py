from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


REQUIRED_FIELDS = ("id", "package", "reason", "owner", "expires_on")


@dataclass(frozen=True)
class AllowlistEntry:
    id: str
    package: str
    reason: str
    owner: str
    expires_on: date

    @classmethod
    def from_dict(cls, raw_entry: object) -> "AllowlistEntry":
        if not isinstance(raw_entry, dict):
            raise SystemExit("Each pip-audit allowlist entry must be a JSON object.")
        missing = [field for field in REQUIRED_FIELDS if not raw_entry.get(field)]
        if missing:
            raise SystemExit(f"pip-audit allowlist entry is missing required fields: {missing!r}.")
        try:
            expires_on = date.fromisoformat(str(raw_entry["expires_on"]))
        except ValueError as exc:
            raise SystemExit(
                f"pip-audit allowlist entry {raw_entry.get('id')!r} has an invalid expires_on date."
            ) from exc
        return cls(
            id=str(raw_entry["id"]),
            package=str(raw_entry["package"]),
            reason=str(raw_entry["reason"]),
            owner=str(raw_entry["owner"]),
            expires_on=expires_on,
        )


def load_allowlist(path: Path) -> list[AllowlistEntry]:
    try:
        raw_entries = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"pip-audit allowlist file {path} does not exist.") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"pip-audit allowlist file {path} is not valid JSON: {exc}.") from exc
    if not isinstance(raw_entries, list):
        raise SystemExit("pip-audit allowlist file must contain a JSON list.")
    return [AllowlistEntry.from_dict(entry) for entry in raw_entries]


def validate_allowlist(entries: list[AllowlistEntry], today: date) -> None:
    expired_entries = [entry for entry in entries if entry.expires_on < today]
    if expired_entries:
        expired_details = ", ".join(
            f"{entry.id} ({entry.package}) expired {entry.expires_on.isoformat()}"
            for entry in expired_entries
        )
        raise SystemExit(f"pip-audit allowlist contains expired entries: {expired_details}.")


def build_ignore_args(entries: list[AllowlistEntry]) -> list[str]:
    ignore_args: list[str] = []
    for entry in entries:
        ignore_args.extend(["--ignore-vuln", entry.id])
    return ignore_args


def run_pip_audit(
    *,
    allowlist_path: Path,
    site_packages_path: str,
    output_path: Path | None,
    python_executable: str,
    today: date,
) -> int:
    entries = load_allowlist(allowlist_path)
    validate_allowlist(entries, today)
    command = [python_executable, "-m", "pip_audit", "--path", site_packages_path, *build_ignore_args(entries)]
    completed_process = subprocess.run(command, capture_output=True, text=True)
    combined_output = completed_process.stdout
    if completed_process.stderr:
        combined_output = f"{combined_output}{completed_process.stderr}"
    if output_path is not None:
        output_path.write_text(combined_output, encoding="utf-8")
    sys.stdout.write(combined_output)
    return completed_process.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and enforce the xyce-py pip-audit exception policy.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in ("ignore-args", "validate"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--allowlist",
            type=Path,
            default=Path("security/pip_audit_allowlist.json"),
            help="Path to the JSON allowlist.",
        )
        command_parser.add_argument(
            "--today",
            default=date.today().isoformat(),
            help="Override the policy evaluation date in YYYY-MM-DD format.",
        )

    command_parser = subparsers.add_parser("run")
    command_parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path("security/pip_audit_allowlist.json"),
        help="Path to the JSON allowlist.",
    )
    command_parser.add_argument(
        "--path",
        required=True,
        help="Site-packages path for the environment under audit.",
    )
    command_parser.add_argument(
        "--output",
        type=Path,
        default=Path("pip-audit.txt"),
        help="Optional file to capture pip-audit output.",
    )
    command_parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python executable with pip_audit installed.",
    )
    command_parser.add_argument(
        "--today",
        default=date.today().isoformat(),
        help="Override the policy evaluation date in YYYY-MM-DD format.",
    )

    return parser


def parse_today(today_text: str) -> date:
    try:
        return date.fromisoformat(today_text)
    except ValueError as exc:
        raise SystemExit(f"Invalid --today value {today_text!r}; expected YYYY-MM-DD.") from exc


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    today = parse_today(args.today)

    if args.command == "validate":
        validate_allowlist(load_allowlist(args.allowlist), today)
        return 0

    if args.command == "ignore-args":
        entries = load_allowlist(args.allowlist)
        validate_allowlist(entries, today)
        print(" ".join(build_ignore_args(entries)))
        return 0

    if args.command == "run":
        return run_pip_audit(
            allowlist_path=args.allowlist,
            site_packages_path=args.path,
            output_path=args.output,
            python_executable=args.python_executable,
            today=today,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
