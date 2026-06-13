from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

from ._validation import validate_non_empty_string as _validate_non_empty_string


def _normalize_arguments(arguments: Iterable[str]) -> tuple[str, ...]:
    if not isinstance(arguments, list):
        raise TypeError("arguments must be provided as a list of strings.")
    return tuple(
        _validate_non_empty_string(argument, "arguments item")
        for argument in arguments
    )


def _resolve_working_dir(working_dir: Path | str | None) -> Path:
    if working_dir is None:
        return Path.cwd()
    path = Path(working_dir)
    if not path.exists():
        raise FileNotFoundError(f"working_dir does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"working_dir must be a directory: {path}")
    return path.resolve()


def _resolve_expected_output(working_dir: Path, expected_output: Path | str | None) -> Path | None:
    if expected_output is None:
        return None
    output_path = Path(expected_output)
    if not output_path.is_absolute():
        output_path = working_dir / output_path
    return output_path


@dataclass(frozen=True)
class XdmTranslationResult:
    command: tuple[str, ...]
    working_dir: Path
    stdout: str
    stderr: str
    elapsed_sec: float
    output_path: Path | None = None

    def translated_netlist_text(self) -> str:
        if self.output_path is None:
            raise ValueError("No expected output path was declared for this translation.")
        return self.output_path.read_text()


@dataclass(frozen=True)
class XdmTranslator:
    xdm_path: str = "xdm"

    def __post_init__(self):
        object.__setattr__(self, "xdm_path", _validate_non_empty_string(self.xdm_path, "xdm_path"))

    def run(
        self,
        arguments: list[str],
        *,
        working_dir: Path | str | None = None,
        expected_output: Path | str | None = None,
    ) -> XdmTranslationResult:
        arguments = _normalize_arguments(arguments)
        resolved_working_dir = _resolve_working_dir(working_dir)
        output_path = _resolve_expected_output(resolved_working_dir, expected_output)

        command = (self.xdm_path, *arguments)
        started_at = time.perf_counter()
        completed_process = subprocess.run(
            list(command),
            cwd=resolved_working_dir,
            capture_output=True,
            text=True,
        )
        elapsed_sec = time.perf_counter() - started_at

        if completed_process.returncode != 0:
            raise XdmTranslationError(
                f"XDM failed (code {completed_process.returncode}).",
                command=command,
                returncode=completed_process.returncode,
                stdout=completed_process.stdout,
                stderr=completed_process.stderr,
                working_dir=resolved_working_dir,
                elapsed_sec=elapsed_sec,
            )

        if output_path is not None and not output_path.exists():
            raise FileNotFoundError(f"Expected XDM output was not produced at {output_path}.")

        return XdmTranslationResult(
            command=command,
            working_dir=resolved_working_dir,
            stdout=completed_process.stdout,
            stderr=completed_process.stderr,
            elapsed_sec=elapsed_sec,
            output_path=output_path,
        )


class XdmTranslationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        command: tuple[str, ...],
        returncode: int,
        stdout: str,
        stderr: str,
        working_dir: Path,
        elapsed_sec: float,
    ):
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.working_dir = working_dir
        self.elapsed_sec = elapsed_sec
