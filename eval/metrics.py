"""Small dependency-free metrics for golden-case evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def get_path(value: Any, path: str) -> Any:
    """Read a dotted path from nested mappings, objects, or sequences."""

    if isinstance(value, Mapping) and path in value:
        return value[path]

    current = value
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, str):
            current = current[int(part)]
        else:
            current = getattr(current, part)
    return current


def compare_expected(actual: Any, expected: Mapping[str, Any]) -> list[str]:
    """Return structural/value mismatches for the expected dotted paths."""

    failures = []
    for path, expected_value in expected.items():
        try:
            actual_value = get_path(actual, path)
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as error:
            failures.append(f"{path}: unavailable ({error})")
            continue
        if actual_value != expected_value:
            failures.append(f"{path}: expected {expected_value!r}, got {actual_value!r}")
    return failures


def score_case(actual: Any, expected: Mapping[str, Any]) -> tuple[int, int, list[str]]:
    """Return passed checks, total checks, and mismatch details."""

    failures = compare_expected(actual, expected)
    return len(expected) - len(failures), len(expected), failures
