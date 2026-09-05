"""Explicitly authorize a designated Google or Microsoft demo account for read-only access."""

import argparse
from pathlib import Path

from app.mcp.oauth import DEFAULT_TOKEN_DIR, OAuthError, connect_account


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["google", "microsoft"])
    parser.add_argument("--token-dir", type=Path, default=DEFAULT_TOKEN_DIR)
    args = parser.parse_args()
    try:
        connect_account(args.provider, args.token_dir)
    except OAuthError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"{args.provider} OAuth saved privately. Verify account bindings before syncing.")


if __name__ == "__main__":
    main()
