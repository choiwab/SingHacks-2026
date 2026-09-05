"""Explicit demo-account sign-in and noninteractive, read-only OAuth token refresh."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import msal
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
]
MICROSOFT_SCOPES = ["User.Read", "Mail.Read", "Calendars.Read"]
DEFAULT_TOKEN_DIR = Path(".local/connectors")
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class OAuthError(ValueError):
    """Safe diagnostic that does not contain provider responses or credentials."""


@contextmanager
def _locked_path(provider: str, token_dir: Path) -> Iterator[Path]:
    if provider not in {"google", "microsoft"}:
        raise OAuthError("Unknown OAuth provider")
    if token_dir.is_symlink():
        raise OAuthError("Token directory must not be a symbolic link")
    token_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    token_dir.chmod(0o700)
    path = token_dir / f"{provider}.json"
    if path.is_symlink():
        raise OAuthError("Token file must not be a symbolic link")
    # ponytail: local POSIX file lock; use a managed vault for multi-host deployments.
    fd = os.open(token_dir / f"{provider}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield path
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _save(path: Path, text: str) -> None:
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temporary:
            name = temporary.name
            os.fchmod(temporary.fileno(), 0o600)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def _google_credentials(path: Path) -> Credentials:
    info = json.loads(path.read_text())
    if info.get("token_uri") not in {
        GOOGLE_TOKEN_URI,
        "https://accounts.google.com/o/oauth2/token",
    }:
        raise OAuthError("Google token endpoint is not allowed; reconnect the account")
    if set(info.get("scopes", [])) != set(GOOGLE_SCOPES):
        raise OAuthError("Google cached scopes differ from the read-only connector scopes")
    # Do not allow credential-file endpoint/universe overrides to route a refresh token elsewhere.
    safe = {
        key: info[key]
        for key in ("token", "refresh_token", "client_id", "client_secret", "expiry", "scopes")
        if key in info
    }
    safe["token_uri"] = GOOGLE_TOKEN_URI
    return Credentials.from_authorized_user_info(safe, scopes=GOOGLE_SCOPES)


def _microsoft_app(path: Path):
    client_id = str(UUID(os.environ["MICROSOFT_CLIENT_ID"]))
    tenant_id = str(UUID(os.environ["MICROSOFT_TENANT_ID"]))
    cache = msal.SerializableTokenCache()
    if path.exists():
        cache.deserialize(path.read_text())
    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
        instance_discovery=False,
        timeout=20,
    )
    return app, cache


def access_token(provider: str, token_dir: Path = DEFAULT_TOKEN_DIR) -> str:
    """Return or refresh a cached token. Never open a browser or initiate device login."""
    try:
        with _locked_path(provider, token_dir) as path:
            if not path.is_file():
                raise OAuthError("Account has not been connected")
            path.chmod(0o600)
            if provider == "google":
                credentials = _google_credentials(path)
                if not credentials.valid:
                    credentials.refresh(Request())
                    _save(path, credentials.to_json())
                if credentials.valid and credentials.token:
                    return credentials.token
            else:
                app, cache = _microsoft_app(path)
                accounts = app.get_accounts()
                if len(accounts) != 1:
                    raise OAuthError("Exactly one designated Microsoft demo account is required")
                result = app.acquire_token_silent(MICROSOFT_SCOPES, account=accounts[0])
                if cache.has_state_changed:
                    _save(path, cache.serialize())
                if (
                    result
                    and isinstance(result.get("access_token"), str)
                    and result["access_token"]
                ):
                    return result["access_token"]
    except Exception:
        # Provider exceptions may embed access tokens, refresh tokens, or authorization URLs.
        raise OAuthError(
            "OAuth unavailable. Configure the provider and run "
            "python -m scripts.connect_accounts google|microsoft explicitly."
        ) from None
    raise OAuthError("OAuth expired or consent required; reconnect the designated demo account")


def connect_account(provider: str, token_dir: Path = DEFAULT_TOKEN_DIR) -> None:
    """Interactive entry point only. Do not call from a server, agent, or background sync."""
    try:
        with _locked_path(provider, token_dir) as path:
            if provider == "google":
                config = json.loads(Path(os.environ["GOOGLE_OAUTH_CLIENT_FILE"]).read_text())
                installed = config["installed"]
                if installed["auth_uri"] != "https://accounts.google.com/o/oauth2/auth":
                    raise OAuthError("Google authorization endpoint is not allowed")
                if installed["token_uri"] not in {
                    GOOGLE_TOKEN_URI,
                    "https://accounts.google.com/o/oauth2/token",
                }:
                    raise OAuthError("Google token endpoint is not allowed")
                safe_config = {
                    "installed": {
                        "client_id": installed["client_id"],
                        "client_secret": installed["client_secret"],
                        "auth_uri": installed["auth_uri"],
                        "token_uri": GOOGLE_TOKEN_URI,
                    }
                }
                flow = InstalledAppFlow.from_client_config(
                    safe_config, GOOGLE_SCOPES, autogenerate_code_verifier=True
                )
                credentials = flow.run_local_server(
                    host="127.0.0.1",
                    port=0,
                    open_browser=True,
                    authorization_prompt_message="Complete Google consent in the opened browser.",
                    timeout_seconds=180,
                    prompt="consent",
                )
                if not credentials.refresh_token or not credentials.has_scopes(GOOGLE_SCOPES):
                    raise OAuthError("Google offline access and both read-only scopes are required")
                _save(path, credentials.to_json())
            else:
                app, cache = _microsoft_app(path)
                flow = app.initiate_device_flow(scopes=MICROSOFT_SCOPES)
                if "user_code" not in flow:
                    raise OAuthError("Microsoft device authorization could not start")
                # Only the explicitly invoked setup command displays the short-lived user code.
                print("Open https://microsoft.com/devicelogin and enter: " + flow["user_code"])
                result = app.acquire_token_by_device_flow(flow)
                if not result or not result.get("access_token"):
                    raise OAuthError("Microsoft authorization did not succeed")
                if len(app.get_accounts()) != 1:
                    raise OAuthError(
                        "Use one designated Microsoft demo account per token directory"
                    )
                _save(path, cache.serialize())
    except Exception:
        raise OAuthError(
            "OAuth setup failed. Check the provider configuration, read-only consent, "
            "and designated demo account; credentials were not printed."
        ) from None
