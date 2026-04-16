from __future__ import annotations

import re
from pathlib import Path


README_PATH = Path(__file__).resolve().parents[1] / "README.md"


def extract_python_snippet(section_heading: str) -> str:
    readme = README_PATH.read_text(encoding="utf-8")
    section_marker = f"## {section_heading}\n"
    section_start = readme.find(section_marker)
    if section_start == -1:
        raise AssertionError(f"Could not find README section {section_heading!r}.")

    section_body_start = section_start + len(section_marker)
    remainder = readme[section_body_start:]
    next_heading = re.search(r"^##\s", remainder, flags=re.MULTILINE)
    section_body = remainder[: next_heading.start()] if next_heading else remainder

    match = re.search(r"```python\n(.*?)```", section_body, flags=re.DOTALL)
    if match is None:
        raise AssertionError(f"Could not find a Python code block under README section {section_heading!r}.")
    return match.group(1).strip()
