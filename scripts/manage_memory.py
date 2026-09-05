"""Import an explicitly supplied local interaction, or inspect its immutable version history."""

import argparse
import json
from pathlib import Path

from app.mcp.records import CommunicationRecord
from app.mcp.store import MemoryStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", type=Path, default=Path("data/generated/memory"))
    actions = parser.add_subparsers(dest="action", required=True)
    ingest = actions.add_parser("import", help="Import one normalized CommunicationRecord JSON")
    ingest.add_argument("file", type=Path)
    history = actions.add_parser("history")
    history.add_argument("client_id")
    history.add_argument("record_id")
    args = parser.parse_args()
    store = MemoryStore(args.memory_dir / "records.sqlite3")
    if args.action == "import":
        record = CommunicationRecord.model_validate_json(args.file.read_text())
        if record.provenance == "dataset" or record.id.startswith("notes:N-"):
            parser.error("Original dataset notes are read-only; use a new interaction ID")
        store.put(record)
        print(f"Stored {record.id} version {record.version} for {record.client_id} as Cached")
    else:
        print(
            json.dumps(
                [r.model_dump(mode="json") for r in store.history(args.client_id, args.record_id)],
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
