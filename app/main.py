"""FastAPI application factory: health, review persistence, and frontend serving."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from app.mcp.records import Source
from app.mcp.seed import seed_demo_memory
from app.mcp.service import load_memory
from app.mcp.store import MemoryStore
from app.pipeline.actions import DemoUpdateRequest, ReviewActionRequest, ReviewActionResponse
from app.pipeline.api_schemas import (
    ClientMemory,
    CommunicationsResponse,
    DemoViewModel,
    NamedCommunicationRecord,
)
from app.pipeline.features import AnalyticsProvider, legacy_analytics
from app.pipeline.graph_adapter import AgentHooks
from app.pipeline.history import ClientHistory, load_client_history
from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.member2_bridge import member2_hooks
from app.pipeline.publish import read_latest
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import ReviewRequest
from app.pipeline.view_model import build_view_model
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
    curated_dir: Path | None = None,
    overlay_dir: Path | None = None,
    memory_dir: Path | None = None,
    analytics: AnalyticsProvider = legacy_analytics,
    agents: AgentHooks | None = None,
) -> FastAPI:
    """Create an isolated app; all I/O occurs inside its lifespan."""
    database = database or source_dir / "generated" / "reviews.sqlite3"

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        ledger = ReviewLedger(database)
        store = ArtifactStore(curated_dir or source_dir / "generated/curated")
        memory = MemoryStore((memory_dir or source_dir / "generated/memory") / "records.sqlite3")
        seed_demo_memory(memory, source_dir / "fixtures/connected/records.json")

        def communications(client_id: str, cutoff: datetime, revision: str):
            return load_memory(
                source_dir,
                memory,
                client_id,
                datetime.combine(cutoff.date(), time.min, tzinfo=UTC),
                revision,
                connected=None,
            )

        runtime = PipelineRuntime(
            store,
            ledger,
            source_dir=source_dir,
            as_of=as_of,
            overlay_dir=overlay_dir,
            analytics=analytics,
            agents=agents or member2_hooks(store, load_communications=communications),
            load_communications=communications if agents is None else None,
        )
        application.state.memory_store = memory
        application.state.review_ledger = ledger
        application.state.pipeline_runtime = runtime
        try:
            if read_latest(store.root) is None:
                runtime.seed()
            else:
                runtime.prepare_current()
            yield
        finally:
            ledger.close()

    application = FastAPI(title="Client Future Room", version="0.2.0", lifespan=lifespan)

    @application.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "as_of": as_of.isoformat()}

    def view(runtime: PipelineRuntime, *, updating: bool = False) -> DemoViewModel:
        with runtime.lock:
            return build_view_model(
                runtime.store, runtime.ledger, source_dir=runtime.source_dir, updating=updating
            )

    @application.get("/api/app", response_model=DemoViewModel)
    def app_data(request: Request) -> DemoViewModel:
        return view(request.app.state.pipeline_runtime)

    def memory_for(request: Request, client_id: str) -> ClientMemory:
        runtime: PipelineRuntime = request.app.state.pipeline_runtime
        with runtime.lock:
            manifest = runtime.store.load_manifest()
            if client_id not in manifest.client_ids:
                raise HTTPException(status_code=404, detail="Client not found")
            cutoff = datetime.combine(manifest.as_of, time.min, tzinfo=UTC)
            context = load_memory(
                source_dir,
                request.app.state.memory_store,
                client_id,
                cutoff,
                manifest.run_id,
                connected=None,
            )
            sources = context.sources.copy()
            sources.setdefault("outlook", "Not connected")
            return ClientMemory(
                client_id=client_id,
                as_of=cutoff,
                **context.model_dump(exclude={"sources"}),
                sources=sources,
            )

    @application.get("/api/clients/{client_id}/memory", response_model=ClientMemory)
    def client_memory(client_id: str, request: Request) -> ClientMemory:
        return memory_for(request, client_id)

    @application.get("/api/communications", response_model=CommunicationsResponse)
    def communications_data(
        request: Request, source: Source | None = None
    ) -> CommunicationsResponse:
        runtime: PipelineRuntime = request.app.state.pipeline_runtime
        with runtime.lock:
            manifest = runtime.store.load_manifest()
            records = []
            for client_id in manifest.client_ids:
                name = runtime.store.load_curated_bundle(
                    client_id, run_id=manifest.run_id
                ).profile.client_name
                context = memory_for(request, client_id)
                records.extend(
                    NamedCommunicationRecord(**record.model_dump(), client_name=name)
                    for record in context.records
                    if source is None or record.source == source
                )
            records.sort(
                key=lambda record: (record.scheduled_at or record.occurred_at, record.id),
                reverse=True,
            )
            return CommunicationsResponse(
                as_of=datetime.combine(manifest.as_of, time.min, tzinfo=UTC), records=records
            )

    @application.get("/api/clients/{client_id}/history", response_model=ClientHistory)
    def client_history(
        client_id: str,
        request: Request,
        run_id: str | None = Query(default=None, pattern=r"^[a-f0-9]{12}$"),
    ) -> ClientHistory:
        runtime: PipelineRuntime = request.app.state.pipeline_runtime
        try:
            with runtime.lock:
                return load_client_history(runtime.store, runtime.ledger, client_id, run_id=run_id)
        except ArtifactNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/api/demo/update", response_model=DemoViewModel)
    def demo_update(payload: DemoUpdateRequest, request: Request) -> DemoViewModel:
        runtime: PipelineRuntime = request.app.state.pipeline_runtime
        try:
            with runtime.lock:
                runtime.update() if payload.action == "apply" else runtime.reset()
                return view(runtime, updating=True)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post("/api/reviews", response_model=ReviewActionResponse)
    def review(payload: ReviewActionRequest, request: Request) -> ReviewActionResponse:
        runtime: PipelineRuntime = request.app.state.pipeline_runtime
        try:
            return ReviewActionResponse.model_validate(
                runtime.review(ReviewRequest.model_validate(payload.model_dump()))
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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
