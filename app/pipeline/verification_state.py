"""One strict interpretation of verification readiness across reads and reviews."""

from collections.abc import Mapping
from typing import Any


def verification_passed(report: Mapping[str, Any]) -> bool:
    """Only an explicit passing report with individually passing checks grants readiness."""
    if report.get("passed") is not True or report.get("errors"):
        return False
    checks = report.get("checks", [])
    if isinstance(checks, dict):
        checks = list(checks.values())
    if not isinstance(checks, list):
        return False
    return all(
        check is True
        or (isinstance(check, dict) and check.get("passed") is True and not check.get("errors"))
        for check in checks
    )
