"""Serializable state for Member 2's graph; durable storage is supplied by Member 3."""

from operator import add
from typing import Annotated, Any, NotRequired, TypedDict


class AgentState(TypedDict):
    run_id: str
    client_id: str
    as_of: str
    revision: NotRequired[str]
    bundle: NotRequired[dict[str, Any]]
    connected_context: NotRequired[dict[str, Any]]
    memory_index: NotRequired[dict[str, Any]]
    section_versions: NotRequired[dict[str, str]]
    input_versions: NotRequired[dict[str, str]]
    changed_records: NotRequired[list[str]]
    processing_mode: NotRequired[str]
    change_kind: NotRequired[str]
    insights: NotRequired[list[dict[str, Any]]]
    pack: NotRequired[dict[str, Any] | None]
    pack_version: NotRequired[str | None]
    last_approved: NotRequired[dict[str, Any] | None]
    prior_status: NotRequired[str]
    context_failed: NotRequired[bool]
    status: NotRequired[str]
    issues: NotRequired[list[str]]
    verification: NotRequired[dict[str, Any] | None]
    review: NotRequired[dict[str, Any] | None]
    review_events: NotRequired[list[dict[str, Any]]]
    history: NotRequired[list[dict[str, Any]]]
    generation_note: NotRequired[str]
    trace: Annotated[list[dict[str, Any]], add]
