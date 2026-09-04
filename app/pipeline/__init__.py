"""Deterministic data pipeline: ingest, validate, identify evidence, and publish.

Owned by Member 3 (data team, pipeline engineering). This package never writes prose and
never defines a financial formula; formulas live in ``app.analytics`` and are only published
from here. Run ``python -m app.pipeline run`` to load and validate the raw sources.
"""

from app.pipeline.errors import SourceDiagnostic, SourceValidationError
from app.pipeline.evidence import add_evidence, evidence_id, native, record, slug
from app.pipeline.schemas import (
    ContractModel,
    Evidence,
    ReviewRecord,
    ReviewRequest,
    ReviewResponse,
)
from app.pipeline.sources import SOURCE_FILES, TABLE_NAMES, load_sources, source_versions

__all__ = [
    "SOURCE_FILES",
    "TABLE_NAMES",
    "ContractModel",
    "Evidence",
    "ReviewRecord",
    "ReviewRequest",
    "ReviewResponse",
    "SourceDiagnostic",
    "SourceValidationError",
    "add_evidence",
    "evidence_id",
    "load_sources",
    "native",
    "record",
    "slug",
    "source_versions",
]
