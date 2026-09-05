"""FastAPI application factory: health, review persistence, and frontend serving."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.pipeline.schemas import ReviewRequest, ReviewResponse
from app.pipeline.sources import load_sources
from app.store import ReviewLedger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FRONTEND_DIST = ROOT / "frontend" / "dist"
AS_OF = date(2026, 8, 26)


def create_app(
    *,
    source_dir: Path = DATA,
    as_of: date = AS_OF,
    database: Path | str | None = None,
    frontend_dist: Path = FRONTEND_DIST,
) -> FastAPI:
    """Create an isolated app; all I/O occurs inside its lifespan."""
    database = database or source_dir / "generated" / "reviews.sqlite3"

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        tables, _notes = load_sources(source_dir, as_of=as_of)
        ledger = ReviewLedger(database)
        ledger.import_legacy_json(source_dir / "generated" / "review_log.json")
        application.state.client_ids = frozenset(tables["clients"]["client_id"].astype(str))
        application.state.review_ledger = ledger
        try:
            yield
        finally:
            ledger.close()

    application = FastAPI(title="Client Future Room", version="0.2.0", lifespan=lifespan)

    @application.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "as_of": as_of.isoformat()}

    @application.post("/api/reviews", response_model=ReviewResponse)
    async def review(payload: ReviewRequest, request: Request) -> ReviewResponse:
        client_ids: frozenset[str] = request.app.state.client_ids
        if payload.client_id not in client_ids:
            raise HTTPException(status_code=404, detail="Client not found")
        ledger: ReviewLedger = request.app.state.review_ledger
        return ReviewResponse(review=ledger.append(payload, rm="Priscilla Ong"))

    @application.get("/{frontend_path:path}", include_in_schema=False, response_model=None)
    async def frontend(frontend_path: str) -> FileResponse | HTMLResponse:
        """Serve Vite output and fall back to its index for client-side routes."""
        if frontend_path == "api" or frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        root = frontend_dist.resolve()
        index = root / "index.html"
        if not index.is_file():
            return HTMLResponse(
                "Frontend build not found. Run `pnpm dev` or `pnpm build`.",
                status_code=503,
            )

        requested = (root / frontend_path).resolve()
        if requested.is_relative_to(root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index)

    return application


# ASGI discovery only. Creating this object performs no source or persistence I/O.
app = create_app()
