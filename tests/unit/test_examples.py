from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.unit


EXAMPLES_DIR = Path("examples")
NOTEBOOKS = sorted(EXAMPLES_DIR.glob("*.ipynb"))


def _cell_source(cell: dict[str, object]) -> str:
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(str(line) for line in source)
    return str(source)


def test_example_notebooks_exist_for_distinct_audiences():
    assert len(NOTEBOOKS) >= 3

    audiences: set[str] = set()
    for notebook_path in NOTEBOOKS:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        markdown = "\n".join(
            _cell_source(cell)
            for cell in notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
        audience_lines = [
            line
            for line in markdown.splitlines()
            if line.startswith("**Audience:**")
        ]
        assert len(audience_lines) == 1, f"{notebook_path} must declare exactly one audience."
        audiences.add(audience_lines[0])

    assert len(audiences) == len(NOTEBOOKS)


def test_example_notebooks_are_clean_valid_json_with_compilable_code_cells():
    for notebook_path in NOTEBOOKS:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        assert notebook["nbformat"] == 4
        assert isinstance(notebook["cells"], list)
        assert notebook["cells"], f"{notebook_path} must contain cells."

        for index, cell in enumerate(notebook["cells"]):
            assert cell["cell_type"] in {"markdown", "code"}
            if cell["cell_type"] != "code":
                continue

            assert cell["execution_count"] is None
            assert cell["outputs"] == []
            compile(
                _cell_source(cell),
                f"{notebook_path}:cell-{index}",
                "exec",
            )
