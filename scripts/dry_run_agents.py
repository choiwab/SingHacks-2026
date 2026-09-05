"""Run every Client through the existing offline agent graph, stopping before RM approval."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Any

from app.pipeline.loaders import ArtifactStore
from app.pipeline.runner import run_pipeline
from scripts.run_client_flow import ROOT, build_data_flow


def dry_run_agents(source_dir: Path, as_of: date, *, run_id: str | None = None) -> dict[str, Any]:
    started = perf_counter()
    curated_dir = source_dir / "generated/curated"
    manifest = (
        ArtifactStore(curated_dir).load_manifest(run_id)
        if run_id
        else run_pipeline(
            source_dir=source_dir, as_of=as_of, curated_dir=curated_dir, activate=False
        )
    )
    if manifest.as_of != as_of:
        raise ValueError("Pinned Pipeline Run and requested As-of Date differ")
    pipeline_seconds = perf_counter() - started
    graph = build_data_flow(source_dir, live_generation=False)
    clients = []
    for client_id in manifest.client_ids:
        client_started = perf_counter()
        state = graph.invoke(
            {
                "run_id": manifest.run_id,
                "client_id": client_id,
                "as_of": as_of.isoformat(),
                "revision": manifest.run_id,
                "trace": [],
            },
            config={"configurable": {"thread_id": f"dry-run:{client_id}"}},
        )
        pack = state.get("pack") or {}
        verification = state.get("verification") or {"passed": False, "issues": []}
        clients.append(
            {
                "client_id": client_id,
                "status": state.get("status", "needs_confirmation"),
                "review_required": bool(state.get("__interrupt__")),
                "selected_signals": [item["signal_id"] for item in pack.get("insights", [])],
                "information_request_codes": sorted(
                    {item["code"] for item in pack.get("information_requests", [])}
                ),
                "verification": verification,
                "issues": state.get("issues", []),
                "elapsed_seconds": round(perf_counter() - client_started, 3),
            }
        )
    return {
        "pipeline_run_id": manifest.run_id,
        "as_of": as_of.isoformat(),
        "generation_mode": "deterministic",
        "data_provenance": "Hackathon synthetic dataset, not live client systems",
        "client_count": len(clients),
        "all_awaiting_review": all(
            client["status"] == "awaiting_review"
            and client["review_required"]
            and client["verification"]["passed"]
            for client in clients
        ),
        "pipeline_seconds": round(pipeline_seconds, 3),
        "total_seconds": round(perf_counter() - started, 3),
        "clients": clients,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 8, 26))
    parser.add_argument("--run-id", help="Reuse this immutable Pipeline Run")
    parser.add_argument("--output", type=Path, help="Write the summary JSON to this path")
    args = parser.parse_args()
    result = dry_run_agents(args.source_dir, args.as_of, run_id=args.run_id)
    document = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        print(
            f"{result['client_count']} Clients, all awaiting review: "
            f"{result['all_awaiting_review']}; {args.output}"
        )
    else:
        print(document, end="")
    if not result["all_awaiting_review"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
