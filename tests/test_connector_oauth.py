"""OAuth SDKs are mocked: tests never authorize accounts or contact providers."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.mcp import oauth


def google_info(**overrides):
    return {
        "token": "private-access",
        "refresh_token": "private-refresh",
        "client_id": "demo-client",
        "client_secret": "private-client-secret",
        "token_uri": oauth.GOOGLE_TOKEN_URI,
        "scopes": oauth.GOOGLE_SCOPES,
        **overrides,
    }


def write_google(path, info=None):
    path.mkdir(exist_ok=True)
    (path / "google.json").write_text(json.dumps(info or google_info()))


def test_google_cached_access_never_starts_login(tmp_path, monkeypatch, capsys):
    write_google(tmp_path)
    credentials = Mock(valid=True, token="private-access")
    load = Mock(return_value=credentials)
    monkeypatch.setattr(oauth.Credentials, "from_authorized_user_info", load)
    setup = Mock(side_effect=AssertionError("interactive login forbidden"))
    monkeypatch.setattr(oauth.InstalledAppFlow, "from_client_config", setup)
    assert oauth.access_token("google", tmp_path) == "private-access"
    credentials.refresh.assert_not_called()
    setup.assert_not_called()
    assert load.call_args.args[0]["token_uri"] == oauth.GOOGLE_TOKEN_URI
    assert not capsys.readouterr().out
    assert (tmp_path.stat().st_mode & 0o777) == 0o700
    assert ((tmp_path / "google.json").stat().st_mode & 0o777) == 0o600


def test_google_refresh_is_persisted(tmp_path, monkeypatch):
    write_google(tmp_path)
    credentials = Mock(valid=False, token=None)

    def refresh(_):
        credentials.valid = True
        credentials.token = "refreshed-access"

    credentials.refresh.side_effect = refresh
    credentials.to_json.return_value = json.dumps(google_info(token="refreshed-access"))
    monkeypatch.setattr(
        oauth.Credentials, "from_authorized_user_info", Mock(return_value=credentials)
    )
    assert oauth.access_token("google", tmp_path) == "refreshed-access"
    assert json.loads((tmp_path / "google.json").read_text())["token"] == "refreshed-access"
    assert (tmp_path / "google.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "info",
    [
        google_info(token_uri="https://attacker.invalid/steal"),
        google_info(scopes=["https://mail.google.com/"]),
    ],
)
def test_rejects_untrusted_google_endpoints_and_scopes(tmp_path, monkeypatch, info):
    write_google(tmp_path, info)
    loader = Mock(side_effect=AssertionError("must validate before SDK"))
    monkeypatch.setattr(oauth.Credentials, "from_authorized_user_info", loader)
    with pytest.raises(oauth.OAuthError, match="OAuth unavailable"):
        oauth.access_token("google", tmp_path)
    loader.assert_not_called()


def test_oauth_background_errors_redact_provider_secrets(tmp_path, monkeypatch, capsys):
    write_google(tmp_path)
    credentials = Mock(valid=False)
    credentials.refresh.side_effect = RuntimeError("private-refresh https://secret.invalid")
    monkeypatch.setattr(
        oauth.Credentials, "from_authorized_user_info", Mock(return_value=credentials)
    )
    with pytest.raises(oauth.OAuthError) as error:
        oauth.access_token("google", tmp_path)
    assert "private-refresh" not in str(error.value)
    assert "secret.invalid" not in str(error.value)
    assert error.value.__suppress_context__
    assert not capsys.readouterr().out


def test_missing_cache_does_not_launch_login(tmp_path, monkeypatch):
    setup = Mock(side_effect=AssertionError("must not sign in"))
    monkeypatch.setattr(oauth.InstalledAppFlow, "from_client_config", setup)
    with pytest.raises(oauth.OAuthError, match="connect_accounts"):
        oauth.access_token("google", tmp_path)
    setup.assert_not_called()


def microsoft_sdk(monkeypatch, tmp_path, accounts=None, result=None):
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "22222222-2222-2222-2222-222222222222")
    (tmp_path / "microsoft.json").write_text("{}")
    cache = Mock(has_state_changed=True)
    cache.serialize.return_value = '{"updated":true}'
    monkeypatch.setattr(oauth.msal, "SerializableTokenCache", Mock(return_value=cache))
    app = Mock()
    app.get_accounts.return_value = accounts if accounts is not None else [{"id": "demo"}]
    app.acquire_token_silent.return_value = result or {"access_token": "ms-private-access"}
    factory = Mock(return_value=app)
    monkeypatch.setattr(oauth.msal, "PublicClientApplication", factory)
    return SimpleNamespace(app=app, cache=cache, factory=factory)


def test_microsoft_silent_refresh_and_fixed_tenant(tmp_path, monkeypatch, capsys):
    sdk = microsoft_sdk(monkeypatch, tmp_path)
    assert oauth.access_token("microsoft", tmp_path) == "ms-private-access"
    assert sdk.factory.call_args.kwargs["authority"] == (
        "https://login.microsoftonline.com/22222222-2222-2222-2222-222222222222"
    )
    sdk.app.acquire_token_silent.assert_called_once_with(
        oauth.MICROSOFT_SCOPES, account={"id": "demo"}
    )
    sdk.app.initiate_device_flow.assert_not_called()
    assert json.loads((tmp_path / "microsoft.json").read_text()) == {"updated": True}
    assert not capsys.readouterr().out


@pytest.mark.parametrize("accounts", [[], [{"id": "one"}, {"id": "two"}]])
def test_microsoft_requires_one_account(tmp_path, monkeypatch, accounts):
    sdk = microsoft_sdk(monkeypatch, tmp_path, accounts=accounts)
    with pytest.raises(oauth.OAuthError):
        oauth.access_token("microsoft", tmp_path)
    sdk.app.acquire_token_silent.assert_not_called()


def test_microsoft_rejects_arbitrary_authority_before_sdk(tmp_path, monkeypatch):
    sdk = microsoft_sdk(monkeypatch, tmp_path)
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "https://attacker.invalid")
    with pytest.raises(oauth.OAuthError):
        oauth.access_token("microsoft", tmp_path)
    sdk.factory.assert_not_called()


def test_google_setup_is_loopback_scoped_and_private(tmp_path, monkeypatch, capsys):
    client_file = tmp_path / "client.json"
    client_file.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "demo",
                    "client_secret": "secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": oauth.GOOGLE_TOKEN_URI,
                }
            }
        )
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_FILE", str(client_file))
    credentials = Mock(refresh_token="private-refresh")
    credentials.has_scopes.return_value = True
    credentials.to_json.return_value = json.dumps(google_info())
    flow = Mock()
    flow.run_local_server.return_value = credentials
    factory = Mock(return_value=flow)
    monkeypatch.setattr(oauth.InstalledAppFlow, "from_client_config", factory)
    oauth.connect_account("google", tmp_path / "tokens")
    assert factory.call_args.args[1] == oauth.GOOGLE_SCOPES
    assert flow.run_local_server.call_args.kwargs["host"] == "127.0.0.1"
    assert flow.run_local_server.call_args.kwargs["port"] == 0
    assert (tmp_path / "tokens/google.json").stat().st_mode & 0o777 == 0o600
    assert not capsys.readouterr().out


def test_microsoft_setup_prints_only_user_code_and_saves(tmp_path, monkeypatch, capsys):
    sdk = microsoft_sdk(monkeypatch, tmp_path)
    sdk.app.initiate_device_flow.return_value = {
        "user_code": "DEMO-CODE",
        "device_code": "private-device-code",
        "message": "untrusted-provider-message",
    }
    sdk.app.acquire_token_by_device_flow.return_value = {"access_token": "private-access"}
    oauth.connect_account("microsoft", tmp_path)
    output = capsys.readouterr().out
    assert "DEMO-CODE" in output
    assert "private" not in output
    assert "untrusted" not in output
    assert (tmp_path / "microsoft.json").stat().st_mode & 0o777 == 0o600


def test_token_symlinks_are_rejected(tmp_path):
    target = tmp_path / "target"
    target.write_text("keep unchanged")
    directory = tmp_path / "tokens"
    directory.mkdir()
    (directory / "google.json").symlink_to(target)
    with pytest.raises(oauth.OAuthError):
        oauth.access_token("google", directory)
    assert target.read_text() == "keep unchanged"


def test_setup_refuses_google_client_endpoint_override(tmp_path, monkeypatch):
    client_file = tmp_path / "client.json"
    client_file.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "demo",
                    "client_secret": "secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://attacker.invalid/token",
                }
            }
        )
    )
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_FILE", str(client_file))
    factory = Mock(side_effect=AssertionError("cannot initiate untrusted login"))
    monkeypatch.setattr(oauth.InstalledAppFlow, "from_client_config", factory)
    with pytest.raises(oauth.OAuthError, match="OAuth setup failed"):
        oauth.connect_account("google", tmp_path / "tokens")
    factory.assert_not_called()


def test_microsoft_consent_failure_stays_noninteractive(tmp_path, monkeypatch, capsys):
    sdk = microsoft_sdk(
        monkeypatch,
        tmp_path,
        result={
            "error": "interaction_required",
            "error_description": "private-token-and-url",
        },
    )
    with pytest.raises(oauth.OAuthError) as error:
        oauth.access_token("microsoft", tmp_path)
    assert "private" not in str(error.value)
    sdk.app.initiate_device_flow.assert_not_called()
    assert not capsys.readouterr().out
