"""Projection build diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProjectionDiagnostic:
    file: str
    code: str
    message: str
    row: int | None = None
    field: str | None = None

    def __str__(self) -> str:
        location = self.file
        if self.row is not None:
            location += f":{self.row}"
        if self.field:
            location += f" [{self.field}]"
        return f"{location}: {self.code}: {self.message}"


class ProjectionBuildError(ValueError):
    """Raised once with every source or contract problem found in a build."""

    def __init__(self, diagnostics: list[ProjectionDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("Projection build failed:\n" + "\n".join(map(str, diagnostics)))
