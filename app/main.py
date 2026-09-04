"""FastAPI entry point for Client Future Room."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.domain import (
    build_action_plan,
    build_case_summary,
    build_connector_previews,
    build_evidence,
    rehearse,
    run_scenario,
    run_specialist_council,
)

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

app = FastAPI(
    title="Client Future Room",
    description="Grounded decision-to-execution intelligence for relationship managers.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class RehearsalRequest(BaseModel):
    opening: Annotated[str, Field(pattern="^(trigger|project|concentration)$")]
    follow_up: Annotated[str | None, Field(pattern="^(challenge|resilience|sell)$")] = None


class TaskPayload(BaseModel):
    id: str
    title: Annotated[str, Field(min_length=3, max_length=180)]
    owner: Annotated[str, Field(min_length=2, max_length=80)]
    due: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    system: str = "CRM task"


class ApprovalRequest(BaseModel):
    tasks: Annotated[list[TaskPayload], Field(min_length=1, max_length=10)]
    acknowledged: bool


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "as_of": "2026-08-26"}


@app.get("/api/case")
async def case() -> dict:
    return {"case": build_case_summary(), "evidence": build_evidence()}


@app.post("/api/prepare")
async def prepare() -> dict:
    return {
        "scenario": run_scenario(),
        "council": await run_specialist_council(),
        "action_plan": build_action_plan(),
        "evidence": build_evidence(),
    }


@app.post("/api/rehearse")
async def rehearsal(request: RehearsalRequest) -> dict:
    try:
        return rehearse(request.opening, request.follow_up)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/action-plan/approve")
async def approve_action_plan(request: ApprovalRequest) -> dict:
    if not request.acknowledged:
        raise HTTPException(
            status_code=422,
            detail="Review the action plan and acknowledge that all connector writes are previews.",
        )
    tasks = [task.model_dump() for task in request.tasks]
    return build_connector_previews(tasks)
