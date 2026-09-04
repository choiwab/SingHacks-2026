"""Public interface for the Monday Brief projection module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from app.monday_brief.errors import ProjectionBuildError, ProjectionDiagnostic
    from app.monday_brief.models import MondayBriefProjection

    build_monday_brief: Callable[..., MondayBriefProjection]
    save_projection: Callable[[MondayBriefProjection, Path], None]

__all__ = [
    "MondayBriefProjection",
    "ProjectionBuildError",
    "ProjectionDiagnostic",
    "build_monday_brief",
    "save_projection",
]


def __getattr__(name: str) -> Any:
    """Load the public interface lazily so the internal pipeline can import policy."""
    if name in {"build_monday_brief", "save_projection"}:
        from app.monday_brief import builder

        return getattr(builder, name)
    if name in {"ProjectionBuildError", "ProjectionDiagnostic"}:
        from app.monday_brief import errors

        return getattr(errors, name)
    if name == "MondayBriefProjection":
        from app.monday_brief.models import MondayBriefProjection

        return MondayBriefProjection
    raise AttributeError(name)
