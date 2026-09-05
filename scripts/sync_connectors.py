"""Explicitly fetch scoped Google/Outlook email and calendars into durable offline memory."""

import argparse
from datetime import UTC, date, datetime, time
from pathlib import Path

from app.mcp.external import read_connectors
from app.mcp.external_common import ConnectorSettings
from app.mcp.store import MemoryStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--token-dir", type=Path, default=Path(".local/connectors"))
    parser.add_argument("--memory-dir", type=Path, default=Path("data/generated/memory"))
    args = parser.parse_args()
    try:
        settings = ConnectorSettings.model_validate_json(args.config.read_text())
        result = read_connectors(
            settings,
            MemoryStore(args.memory_dir / "records.sqlite3"),
            args.client_id,
            datetime.combine(args.as_of, time.max, UTC),
            args.token_dir,
        )
    except (OSError, ValueError):
        parser.exit(
            1,
            "Sync failed. Check OAuth setup, client scopes and provider limits. "
            "No new snapshot published.\n",
        )
    for source, status in result.sources.items():
        print(f"{source}: {status}, {sum(r.source == source for r in result.records)} records")
    print("Snapshot saved for offline replay as Cached. No email or calendar item was changed.")


if __name__ == "__main__":
    main()
