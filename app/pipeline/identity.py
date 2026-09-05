"""Invalidate default analytics artifacts when implementation or reviewed policy changes."""

from hashlib import sha256
from pathlib import Path


def analytics_version(version: str) -> str:
    root = Path(__file__).resolve().parents[2]
    paths = sorted((root / "app/analytics").glob("phase_a*.py"))
    paths.extend(sorted((root / "app/pipeline").glob("*.py")))
    paths.extend(sorted((root / "app/pipeline/stages").glob("*.py")))
    paths.append(root / "notebooks/reference_maps.json")
    digest = sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return f"{version}:phase-a:{digest.hexdigest()[:16]}"
