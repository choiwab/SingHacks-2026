"""Load the cached demo Inbox and Calendar without requiring connector credentials."""

import argparse
from pathlib import Path

from app.mcp.seed import seed_demo_memory
from app.mcp.store import MemoryStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-dir", type=Path, default=Path("data/generated/memory"))
    parser.add_argument(
        "--fixture", type=Path, default=Path("data/fixtures/connected/records.json")
    )
    args = parser.parse_args()
    count = seed_demo_memory(MemoryStore(args.memory_dir / "records.sqlite3"), args.fixture)
    print(f"Imported {count} demo communication records.")


if __name__ == "__main__":
    main()
