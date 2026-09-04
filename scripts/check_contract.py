"""Verify that the committed TypeScript contract matches FastAPI's OpenAPI document."""

from __future__ import annotations

import difflib
import json
import subprocess
import tempfile
from pathlib import Path

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "frontend" / "src" / "generated" / "openapi.ts"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="monday-brief-contract-") as directory:
        temporary = Path(directory)
        document = temporary / "openapi.json"
        generated = temporary / "openapi.ts"
        document.write_text(
            json.dumps(create_app(save_diagnostic=False).openapi(), indent=2) + "\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["pnpm", "exec", "openapi-typescript", str(document), "-o", str(generated)],
            cwd=ROOT,
            check=True,
        )
        expected = COMMITTED.read_text(encoding="utf-8")
        actual = generated.read_text(encoding="utf-8")

    if expected == actual:
        return
    diff = "".join(
        difflib.unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile=str(COMMITTED),
            tofile="generated from FastAPI",
        )
    )
    raise SystemExit(f"Generated TypeScript contract is stale:\n{diff}")


if __name__ == "__main__":
    main()
