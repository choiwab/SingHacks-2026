"""FastAPI entry point for the Monday Brief demo."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.pipeline import GENERATED, build_and_save

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

app = FastAPI(title="Monday Brief", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
app.state.data = build_and_save()
app.state.review_log_path = GENERATED / "review_log.json"


class ReviewRequest(BaseModel):
    client_id: Annotated[str, Field(pattern=r"^CL-\d{4}$")]
    action: Literal["Approve", "Edit", "Reject"]
    text: Annotated[str, Field(max_length=1200)] = ""


def _save_review(payload: ReviewRequest) -> dict[str, str]:
    if payload.client_id not in app.state.data["pre_reads"]:
        raise HTTPException(status_code=404, detail="Client pre-read not found")
    path: Path = app.state.review_log_path
    path.parent.mkdir(exist_ok=True)
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    record = {
        "client_id": payload.client_id,
        "action": payload.action,
        "text": payload.text,
        "rm": "Priscilla Ong",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    records.append(record)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return record


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "as_of": app.state.data["as_of"]}


@app.get("/api/app")
async def application_data() -> dict:
    return app.state.data


@app.post("/api/reviews")
async def review(payload: ReviewRequest) -> dict[str, dict[str, str]]:
    return {"review": _save_review(payload)}
