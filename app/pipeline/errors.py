"""Source validation diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceDiagnostic:
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


class SourceValidationError(ValueError):
    """Raised once with every source problem found in a load."""

    def __init__(self, diagnostics: list[SourceDiagnostic]) -> None:
        self.diagnostics = tuple(diagnostics)
        super().__init__("Source validation failed:\n" + "\n".join(map(str, diagnostics)))
