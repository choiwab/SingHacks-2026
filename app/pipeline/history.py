"""Read-only access to brief versions and operational traces along a client's run lineage."""

from datetime import datetime
from typing import Literal

from pydantic import Field, JsonValue

from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.schemas import ContractModel, ReviewRecord
from app.pipeline.verification_state import verification_passed
from app.store import ReviewLedger


class BriefHistoryVersion(ContractModel):
    run_id: str
    brief_version: int
    origin: Literal["generated", "rm_edited"]
    created_at: datetime
    meeting_brief: dict[str, JsonValue] | None
    verification: dict[str, JsonValue]
    trace: list[JsonValue] = Field(default_factory=list)
    reviews: list[ReviewRecord] = Field(default_factory=list)


class ClientHistory(ContractModel):
    client_id: str
    run_id: str
    versions: list[BriefHistoryVersion]


def load_client_history(
    store: ArtifactStore, ledger: ReviewLedger, client_id: str, *, run_id: str | None = None
) -> ClientHistory:
    """Follow prior_run_id, excluding later runs after a reset; never regenerate content."""
    manifest = store.load_manifest(run_id)
    store.load_curated_bundle(client_id, run_id=manifest.run_id)
    current: str | None = manifest.run_id
    visited: set[str] = set()
    versions = []
    while current is not None:
        if current in visited:
            raise ValueError("Cyclic pipeline run history")
        visited.add(current)
        for brief in reversed(ledger.list_briefs(current, client_id)):
            versions.append(
                BriefHistoryVersion(
                    run_id=current,
                    brief_version=brief.brief_version,
                    origin=brief.origin,
                    created_at=brief.created_at,
                    meeting_brief=brief.body.get("meeting_brief")
                    if verification_passed(brief.verification_report)
                    else None,
                    verification=brief.verification_report,
                    trace=brief.body.get("trace", []),
                    reviews=ledger.list(
                        run_id=current, client_id=client_id, brief_version=brief.brief_version
                    ),
                )
            )
        try:
            current = store.load_change_report(client_id, run_id=current).prior_run_id
        except ArtifactNotFound:
            break
    return ClientHistory(client_id=client_id, run_id=manifest.run_id, versions=versions)
