"""Run the real data-directory node flow without network access or automatic RM approval."""

from __future__ import annotations

import argparse
import json
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from app.agents.contracts import ReviewAction
from app.agents.graph import build_agent_flow
from app.agents.runtime import persistent_data_flow
from app.agents.verification import verify_meeting_pack
from app.agents.versioning import generation_policy_version
from app.pipeline.agent_inputs import load_curated_bundle, load_dataset_notes

ROOT = Path(__file__).resolve().parents[1]


def build_data_flow(source_dir: Path, **kwargs: Any):
    kwargs.setdefault(
        "generation_policy",
        generation_policy_version(live_generation=bool(kwargs.get("live_generation"))),
    )
    return build_agent_flow(
        load_bundle=partial(load_curated_bundle, source_dir),
        load_communications=partial(load_dataset_notes, source_dir),
        verify_pack=verify_meeting_pack,
        **kwargs,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--client-id", default="CL-0003")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 8, 26))
    parser.add_argument("--output", type=Path, help="Write inspectable JSON instead of stdout")
    parser.add_argument("--memory-dir", type=Path, default=ROOT / "data/generated/memory")
    parser.add_argument("--mcp-url", help="Use the live local MCP server for both input loaders")
    parser.add_argument("--review-file", type=Path, help="Explicit, version-bound RM decision JSON")
    args = parser.parse_args()
    review = (
        ReviewAction.model_validate_json(args.review_file.read_text()) if args.review_file else None
    )
    if review and review.client_id != args.client_id:
        parser.error("Review must target the selected Client")
    with persistent_data_flow(args.source_dir, args.memory_dir, mcp_url=args.mcp_url) as graph:
        config: RunnableConfig = {"configurable": {"thread_id": f"sample:{args.client_id}"}}
        # Refresh sources before accepting a persisted review; old versions cannot approve updates.
        result = graph.invoke(
            {
                "run_id": f"sample:{args.client_id}:{args.as_of}",
                "client_id": args.client_id,
                "as_of": args.as_of.isoformat(),
                "revision": "current",
                "trace": [],
            },
            config=config,
        )
        if review:
            if result.get("status") != "awaiting_review" or review.pack_version != result.get(
                "pack_version"
            ):
                parser.error(
                    "Review is stale or no verified pack awaits review. "
                    "Inspect the refreshed run first."
                )
            result = graph.invoke(Command(resume=review.model_dump(mode="json")), config=config)
    output = {key: value for key, value in result.items() if key != "__interrupt__"}
    output["review_required"] = bool(result.get("__interrupt__"))
    output["verifier_kind"] = "source_backed_constrained_wording"
    output["data_provenance"] = "Hackathon synthetic dataset in data/, not live client systems"
    document = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")
        print(f"{result['status']}: {args.output}")
    else:
        print(document, end="")
    if result.get("status") == "needs_confirmation":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
