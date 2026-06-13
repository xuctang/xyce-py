from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import xyce_py


pytestmark = pytest.mark.unit


API_REFERENCE = Path("docs/api-reference.md")


def _public_members_owned_by_package(cls: type) -> set[str]:
    member_names: set[str] = set()
    for name in dir(cls):
        if name.startswith("_"):
            continue

        owner = None
        raw_member = None
        for base in cls.__mro__:
            if name in base.__dict__:
                owner = base
                raw_member = base.__dict__[name]
                break

        if owner is None or not owner.__module__.startswith("xyce_py"):
            continue
        if isinstance(raw_member, property):
            member_names.add(name)
            continue
        if isinstance(raw_member, (classmethod, staticmethod)):
            member_names.add(name)
            continue
        if inspect.isfunction(raw_member):
            member_names.add(name)
    return member_names


def test_api_reference_documents_every_public_export():
    reference = API_REFERENCE.read_text(encoding="utf-8")

    for name in xyce_py.__all__:
        assert f"### `{name}`" in reference, f"Missing API reference heading for {name!r}."


def test_api_reference_documents_public_class_methods_and_properties():
    reference = API_REFERENCE.read_text(encoding="utf-8")

    for class_name in xyce_py.__all__:
        obj = getattr(xyce_py, class_name)
        if not inspect.isclass(obj):
            continue
        for member_name in _public_members_owned_by_package(obj):
            qualified_name = f"{class_name}.{member_name}"
            assert f"`{qualified_name}" in reference, (
                f"Missing API reference entry for {qualified_name!r}."
            )
