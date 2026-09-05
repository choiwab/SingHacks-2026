"""Version the deployed generation and verification policy for safe checkpoint reuse."""

from hashlib import sha256
from pathlib import Path


def generation_policy_version(*, live_generation: bool = False) -> str:
    root = Path(__file__).resolve().parents[2]
    digest = sha256()
    for path in [*sorted((root / "app/agents").glob("*.py")), root / "uv.lock"]:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    mode = "openai" if live_generation else "deterministic"
    return f"phase-a-agents-v2:{digest.hexdigest()[:16]}:{mode}"
