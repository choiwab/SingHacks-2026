"""FastAPI application factory for the Monday Brief demo."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.monday_brief import MondayBriefProjection, build_monday_brief, save_projection
from app.monday_brief.models import ReviewRecord, ReviewRequest
from app.monday_brief.reviews import ReviewLedger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATIC = ROOT / "app" / "static"
AS_OF = date(2026, 8, 26)


def create_app(
    *,
    source_dir: Path = DATA,
    as_of: date = AS_OF,
    database: Path | str | None = None,
    projection: MondayBriefProjection | None = None,
    save_diagnostic: bool = True,
) -> FastAPI:
    """Create an isolated app; all I/O occurs inside its lifespan."""
    database = database or source_dir / "generated" / "reviews.sqlite3"

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        current = projection or build_monday_brief(source_dir, as_of=as_of)
        ledger = ReviewLedger(database)
        ledger.import_legacy_json(source_dir / "generated" / "review_log.json")
        if save_diagnostic:
            save_projection(current, source_dir / "generated" / "app_data.json")
        application.state.projection = current
        application.state.review_ledger = ledger
        try:
            yield
        finally:
            ledger.close()

    application = FastAPI(title="Monday Brief", version="0.2.0", lifespan=lifespan)
    application.mount("/static", StaticFiles(directory=STATIC), name="static")

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @application.get("/api/health")
    async def health(request: Request) -> dict[str, str]:
        current: MondayBriefProjection = request.app.state.projection
        return {"status": "ok", "as_of": current.as_of.isoformat()}

    @application.get("/api/monday-brief", response_model=MondayBriefProjection)
    async def monday_brief(request: Request) -> MondayBriefProjection:
        return request.app.state.projection

    @application.post("/api/reviews")
    async def review(payload: ReviewRequest, request: Request) -> dict[str, ReviewRecord]:
        current: MondayBriefProjection = request.app.state.projection
        if payload.client_id not in current.pre_reads:
            raise HTTPException(status_code=404, detail="Client pre-read not found")
        ledger: ReviewLedger = request.app.state.review_ledger
        return {"review": ledger.append(payload, rm="Priscilla Ong")}

    return application


# ASGI discovery only. Creating this object performs no source or persistence I/O.
app = create_app()
