"""Run, seed, update, reset, or compare persisted pipeline artifacts."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.pipeline.changes import compare_client
from app.pipeline.loaders import ArtifactNotFound, ArtifactStore
from app.pipeline.publish import canonical_json
from app.pipeline.runner import DEFAULT_AS_OF, DEFAULT_SOURCE_DIR, run_pipeline
from app.pipeline.runtime import PipelineRuntime
from app.pipeline.schemas import RunManifest
from app.store import ReviewLedger


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("run", "seed", "update", "reset", "diff"):
        item = subcommands.add_parser(command)
        item.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
        item.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
        item.add_argument("--curated-dir", type=Path)
        item.add_argument("--database", type=Path)
        if command in ("run", "update"):
            item.add_argument("--overlay", type=Path)
        if command == "diff":
            item.add_argument("run_a")
            item.add_argument("run_b")
            item.add_argument("client_id", nargs="?")
    return parser


def _summary(manifest: RunManifest) -> None:
    print(f"run_id: {manifest.run_id}")
    print(f"as_of: {manifest.as_of}")
    print(f"clients: {len(manifest.client_ids)}")
    print(f"errors: {manifest.finding_counts.get('error', 0)}")
    print(f"warnings: {manifest.finding_counts.get('warning', 0)}")
    for issue in manifest.context_issues:
        print(f"context: {issue}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = args.curated_dir or args.source_dir / "generated/curated"
    store = ArtifactStore(root)
    try:
        if args.command == "run":
            _summary(
                run_pipeline(
                    source_dir=args.source_dir,
                    as_of=args.as_of,
                    overlay=args.overlay,
                    curated_dir=root,
                )
            )
        elif args.command == "diff":
            before = store.load_manifest(args.run_a)
            after = store.load_manifest(args.run_b)
            client_ids = (
                [args.client_id]
                if args.client_id
                else sorted(set(before.client_ids) | set(after.client_ids))
            )
            changed = sorted(
                name
                for name in before.source_hashes.keys()
                | after.source_hashes.keys()
                | before.overlay_hashes.keys()
                | after.overlay_hashes.keys()
                if before.source_hashes.get(name) != after.source_hashes.get(name)
                or before.overlay_hashes.get(name) != after.overlay_hashes.get(name)
            )
            reports = [
                compare_client(
                    store.load_fact_bundle(client_id, run_id=args.run_b),
                    store.load_signal_set(client_id, run_id=args.run_b),
                    store.load_fact_bundle(client_id, run_id=args.run_a),
                    store.load_signal_set(client_id, run_id=args.run_a),
                    changed_source_files=changed,
                ).model_dump(mode="json")
                for client_id in client_ids
            ]
            print(canonical_json(reports).decode(), end="")
        else:
            ledger = ReviewLedger(args.database or args.source_dir / "generated/reviews.sqlite3")
            try:
                runtime = PipelineRuntime(
                    store,
                    ledger,
                    source_dir=args.source_dir,
                    as_of=args.as_of,
                    overlay_dir=getattr(args, "overlay", None),
                )
                _summary(getattr(runtime, args.command)())
            finally:
                ledger.close()
        return 0
    except (ValueError, FileNotFoundError, ArtifactNotFound) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
