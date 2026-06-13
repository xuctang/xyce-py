from __future__ import annotations

import pytest

from xyce_py.xdm import XdmTranslationError, XdmTranslator


pytestmark = pytest.mark.unit


def _write_executable(path, content: str):
    path.write_text(content)
    path.chmod(0o755)
    return path


def test_xdm_translator_runs_external_translator_and_reads_expected_output(tmp_path):
    translator_path = _write_executable(
        tmp_path / "fake_xdm",
        """#!/bin/sh
printf 'translated %s %s\\n' "$1" "$2"
printf '* translated netlist\\n.END\\n' > "$2"
""",
    )

    result = XdmTranslator(str(translator_path)).run(
        ["source.sp", "translated.cir"],
        working_dir=tmp_path,
        expected_output="translated.cir",
    )

    assert result.command == (str(translator_path), "source.sp", "translated.cir")
    assert result.working_dir == tmp_path.resolve()
    assert result.stdout == "translated source.sp translated.cir\n"
    assert result.stderr == ""
    assert result.translated_netlist_text() == "* translated netlist\n.END\n"


def test_xdm_translator_defaults_working_dir_to_current_directory(monkeypatch, tmp_path):
    translator_path = _write_executable(
        tmp_path / "fake_xdm",
        """#!/bin/sh
pwd
""",
    )
    monkeypatch.chdir(tmp_path)

    result = XdmTranslator(str(translator_path)).run([])

    assert result.working_dir == tmp_path.resolve()
    assert result.stdout == f"{tmp_path}\n"


def test_xdm_translator_raises_structured_error_for_failed_translation(tmp_path):
    translator_path = _write_executable(
        tmp_path / "fake_xdm_fail",
        """#!/bin/sh
printf 'bad input\\n' >&2
exit 7
""",
    )

    with pytest.raises(XdmTranslationError, match="XDM failed") as caught:
        XdmTranslator(str(translator_path)).run(["source.sp"], working_dir=tmp_path)

    assert caught.value.returncode == 7
    assert caught.value.stderr == "bad input\n"
    assert caught.value.working_dir == tmp_path.resolve()


def test_xdm_translator_rejects_missing_expected_output(tmp_path):
    translator_path = _write_executable(
        tmp_path / "fake_xdm_no_output",
        """#!/bin/sh
exit 0
""",
    )

    with pytest.raises(FileNotFoundError, match="Expected XDM output"):
        XdmTranslator(str(translator_path)).run(
            ["source.sp"],
            working_dir=tmp_path,
            expected_output="missing.cir",
        )


def test_xdm_translator_validates_inputs(tmp_path):
    with pytest.raises(ValueError, match="xdm_path must be a non-empty string"):
        XdmTranslator(" ")

    with pytest.raises(TypeError, match="arguments must be provided as a list"):
        XdmTranslator("xdm").run(("source.sp",), working_dir=tmp_path)

    with pytest.raises(ValueError, match="arguments item must be a non-empty string"):
        XdmTranslator("xdm").run(["source.sp", ""], working_dir=tmp_path)

    with pytest.raises(FileNotFoundError, match="working_dir does not exist"):
        XdmTranslator("xdm").run([], working_dir=tmp_path / "missing")

    file_path = tmp_path / "not-a-directory"
    file_path.write_text("x")
    with pytest.raises(NotADirectoryError, match="working_dir must be a directory"):
        XdmTranslator("xdm").run([], working_dir=file_path)


def test_xdm_translation_result_requires_declared_output_for_text_read(tmp_path):
    translator_path = _write_executable(
        tmp_path / "fake_xdm",
        """#!/bin/sh
exit 0
""",
    )

    result = XdmTranslator(str(translator_path)).run([], working_dir=tmp_path)

    with pytest.raises(ValueError, match="No expected output path"):
        result.translated_netlist_text()
