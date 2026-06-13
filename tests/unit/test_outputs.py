from __future__ import annotations

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from xyce_py.outputs import (
    OutputArtifact,
    OutputSpec,
    collect_output_artifacts,
    load_output_artifact,
    normalize_output_specs,
    read_csv_output,
)


pytestmark = pytest.mark.unit


def test_output_spec_csv_and_text_constructors_preserve_contract_fields():
    csv_spec = OutputSpec.csv("waveforms", "nested/output.csv", required=False)
    text_spec = OutputSpec.text("measurements", "measurements.txt")

    assert csv_spec == OutputSpec("waveforms", "nested/output.csv", "csv", False)
    assert text_spec == OutputSpec("measurements", "measurements.txt", "text", True)


@pytest.mark.parametrize("bad_name", ["", " \t ", None, 3])
def test_output_spec_rejects_invalid_names(bad_name):
    with pytest.raises((TypeError, ValueError)):
        OutputSpec.csv(bad_name, "output.csv")


@pytest.mark.parametrize("bad_path", ["", " \t ", ".", "/tmp/output.csv", "../output.csv", "a/../b.csv", None, 3])
def test_output_spec_rejects_invalid_paths(bad_path):
    with pytest.raises((TypeError, ValueError)):
        OutputSpec.csv("waveforms", bad_path)


def test_output_spec_rejects_unknown_kind_and_non_boolean_required():
    with pytest.raises(ValueError, match="kind must be exactly 'csv' or 'text'"):
        OutputSpec("waveforms", "output.csv", "json")

    with pytest.raises(TypeError, match="required must be a boolean"):
        OutputSpec("waveforms", "output.csv", required="yes")


def test_normalize_output_specs_rejects_non_specs_and_duplicate_names():
    with pytest.raises(TypeError, match="output_specs must contain only OutputSpec"):
        normalize_output_specs([OutputSpec.csv("waveforms", "output.csv"), "output.csv"])

    with pytest.raises(ValueError, match="Duplicate output spec name"):
        normalize_output_specs(
            [
                OutputSpec.csv("waveforms", "one.csv"),
                OutputSpec.text("waveforms", "two.txt"),
            ]
        )


def test_read_csv_output_returns_empty_dataframe_for_missing_and_empty_files(tmp_path):
    assert read_csv_output(tmp_path / "missing.csv").empty

    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("")
    assert read_csv_output(empty_csv).empty


def test_load_output_artifact_reads_csv_and_text_outputs(tmp_path):
    csv_path = tmp_path / "output.csv"
    csv_path.write_text("TIME,V(1)\n0.0,5.0\n")
    text_path = tmp_path / "measure.txt"
    text_path.write_text("rise_time = 1.5e-6\n")

    csv_artifact = load_output_artifact(tmp_path, OutputSpec.csv("waveforms", "output.csv"))
    text_artifact = load_output_artifact(tmp_path, OutputSpec.text("measurements", "measure.txt"))

    assert_frame_equal(csv_artifact.frame, pd.DataFrame({"TIME": [0.0], "V(1)": [5.0]}))
    assert csv_artifact.text is None
    assert text_artifact.text == "rise_time = 1.5e-6\n"
    assert text_artifact.frame is None


def test_load_output_artifact_fails_for_missing_required_output(tmp_path):
    with pytest.raises(FileNotFoundError, match="Required Xyce output 'waveforms' was not produced"):
        load_output_artifact(tmp_path, OutputSpec.csv("waveforms", "missing.csv"))


def test_load_output_artifact_records_missing_optional_output(tmp_path):
    artifact = load_output_artifact(tmp_path, OutputSpec.csv("waveforms", "missing.csv", required=False))

    assert artifact == OutputArtifact(
        spec=OutputSpec.csv("waveforms", "missing.csv", required=False),
        path=tmp_path / "missing.csv",
        exists=False,
    )


def test_collect_output_artifacts_returns_read_only_mapping(tmp_path):
    (tmp_path / "output.csv").write_text("TIME,V(1)\n0.0,5.0\n")
    artifacts = collect_output_artifacts(tmp_path, [OutputSpec.csv("waveforms", "output.csv")])

    with pytest.raises(TypeError):
        artifacts["other"] = artifacts["waveforms"]

    assert artifacts["waveforms"].exists is True


def test_load_output_artifact_propagates_csv_parser_errors(tmp_path):
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text('TIME,V(1)\n0.0,"unterminated\n')

    with pytest.raises(pd.errors.ParserError):
        load_output_artifact(tmp_path, OutputSpec.csv("waveforms", "malformed.csv"))
