"""Minimal pipeline CLI: ``python -m app.pipeline run [--source-dir data] [--as-of DATE]``.

This command reads and validates the raw sources and computes facts in memory. It writes no
files; the seed, update, reset, and diff subcommands are a separate issue.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from app.analytics.facts import fact_engine
from app.pipeline.errors import SourceValidationError
from app.pipeline.sources import load_sources

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DIR = ROOT / "data"
DEFAULT_AS_OF = date(2026, 8, 26)
SPOTLIGHT_CLIENT = "CL-0003"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.pipeline")
    subcommands = parser.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run", help="load, validate, and compute facts in memory")
    run.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    run.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF)
    return parser


def run(source_dir: Path, as_of: date) -> int:
    try:
        tables, _notes = load_sources(source_dir, as_of=as_of)
    except SourceValidationError as exc:
        print(exc, file=sys.stderr)
        return 1
    facts, evidence = fact_engine(tables, as_of)
    fact_count = sum(len(client_facts) for client_facts in facts.values())
    print(f"as_of: {as_of.isoformat()}")
    print(f"clients: {len(facts)}")
    print(f"facts: {fact_count}")
    print(f"evidence: {len(evidence)}")
    print(f"{SPOTLIGHT_CLIENT} facts:")
    for fact in facts.get(SPOTLIGHT_CLIENT, []):
        print(f"  {fact['id']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        return run(args.source_dir, args.as_of)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
