"""Data-team helper for traversing claim-to-evidence references."""

from __future__ import annotations

from typing import Any


def collect_citations(value: Any) -> set[str]:
    """Collect citation identifiers from nested JSON-compatible artifacts."""
    if isinstance(value, dict):
        found = set(value.get("citations", []))
        for nested in value.values():
            found.update(collect_citations(nested))
        return found
    if isinstance(value, list):
        found: set[str] = set()
        for nested in value:
            found.update(collect_citations(nested))
        return found
    return set()
