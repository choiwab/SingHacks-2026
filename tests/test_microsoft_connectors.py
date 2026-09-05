"""Microsoft mail/calendar boundaries, without credentials or external requests."""

from datetime import UTC, datetime

import httpx
import pytest

from app.mcp.external_common import ClientScope, ConnectorSettings, ReadContext
from app.mcp.microsoft_connectors import fetch_outlook_calendar, fetch_outlook_mail

ACCOUNT = "11111111-1111-1111-1111-111111111111"
PROFILE = {"id": ACCOUNT, "mail": "rm@example.com"}
BASE = "https://graph.microsoft.com/v1.0"
AS_OF = datetime(2026, 8, 26, tzinfo=UTC)


def context(handler, *, max_pages=10):
    scope = ClientScope(
        emails=["client@example.com"], outlook_mail=True, outlook_calendar_ids=["calendar-id"]
    )
    settings = ConnectorSettings(
        demo_accounts_only=True,
        microsoft_account_id=ACCOUNT,
        clients={"CL-0003": scope},
        max_pages=max_pages,
    )
    return ReadContext(
        settings=settings,
        client_id="CL-0003",
        scope=scope,
        as_of=AS_OF,
        retrieved_at=AS_OF,
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        token="test-not-a-token",
        provider="microsoft",
    )


def person(email):
    return {"emailAddress": {"address": email}}


def message(**changes):
    return {
        "id": "message-id",
        "receivedDateTime": "2026-08-20T12:00:00Z",
        "sentDateTime": "2026-08-20T11:59:00Z",
        "lastModifiedDateTime": "2026-08-21T12:00:00Z",
        "from": person("client@example.com"),
        "toRecipients": [person("rm@example.com")],
        "isDraft": False,
        "subject": "My goals",
        "body": {"contentType": "html", "content": "<p>Keep goals <b>conservative</b>.</p>"},
        **changes,
    }


def event(**changes):
    return {
        "id": "event-id",
        "createdDateTime": "2025-01-01T12:00:00Z",
        "lastModifiedDateTime": "2025-01-01T12:00:00Z",
        "subject": "Portfolio discussion",
        "organizer": person("rm@example.com"),
        "attendees": [person("CLIENT@example.com")],
        "start": {"dateTime": "2026-09-01T09:00:00.0000000", "timeZone": "UTC"},
        "body": {"contentType": "html", "content": "<p>Discuss funding.</p>"},
        **changes,
    }


def test_mail_pagination_exact_headers_and_read_only():
    seen = []

    def handler(request):
        assert request.method == "GET"
        assert request.headers["authorization"] == "Bearer test-not-a-token"
        seen.append(str(request.url))
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=PROFILE)
        if request.url.path.endswith("/message-id"):
            assert "attachments" not in request.url.params["$select"]
            return httpx.Response(200, json=message())
        if request.url.path.endswith("/sent"):
            return httpx.Response(
                200,
                json=message(
                    id="sent",
                    **{
                        "from": person("rm@example.com"),
                        "toRecipients": [],
                        "bccRecipients": [person("CLIENT@example.com")],
                    },
                ),
            )
        assert request.url.path == "/v1.0/me/messages"
        if "page=2" in str(request.url):
            return httpx.Response(200, json={"value": [message(id="sent")]})
        assert "body" not in request.url.params["$select"]
        assert request.url.params["$orderby"] == "receivedDateTime desc"
        return httpx.Response(
            200,
            json={
                "value": [
                    message(),
                    message(id="future", lastModifiedDateTime="2026-08-27T12:00:00Z"),
                    message(id="draft", isDraft=True),
                    message(id="outsider", **{"from": person("notclient@example.com")}),
                    message(id="no-rm", toRecipients=[]),
                ],
                "@odata.nextLink": f"{BASE}/me/messages?page=2",
            },
        )

    records = fetch_outlook_mail(context(handler))
    assert len(records) == 2
    assert records[0].text.endswith("Keep goals conservative.")
    assert "Subject: My goals" in records[0].text
    assert records[0].source == "outlook"
    assert records[0].availability == "Live"
    assert records[0].provenance == "recorded_live"
    assert records[0].occurred_at == datetime(2026, 8, 21, 12, tzinfo=UTC)
    assert records[0].id != records[1].id
    assert len(seen) == 5


@pytest.mark.parametrize(
    "change",
    [
        {"lastModifiedDateTime": "2026-08-27T12:00:00Z"},
        {"isDraft": True},
        {"from": person("other@example.com")},
    ],
)
def test_mail_rechecks_scope_and_date_when_body_fetched(change):
    def handler(request):
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=PROFILE)
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"value": [message()]})
        return httpx.Response(200, json=message(**change))

    assert fetch_outlook_mail(context(handler)) == []


@pytest.mark.parametrize("fetch", [fetch_outlook_mail, fetch_outlook_calendar])
@pytest.mark.parametrize("status", [401, 403, 429])
def test_auth_and_rate_limit_failures_are_not_empty_success(fetch, status):
    with pytest.raises(httpx.HTTPStatusError):
        fetch(context(lambda request: httpx.Response(status, json={"error": "denied"})))


@pytest.mark.parametrize("fetch", [fetch_outlook_mail, fetch_outlook_calendar])
def test_account_mismatch_stops_before_source_read(fetch):
    def handler(request):
        assert request.url.path == "/v1.0/me"
        return httpx.Response(200, json={"id": "another-account"})

    with pytest.raises(ValueError, match="different RM account"):
        fetch(context(handler))


@pytest.mark.parametrize(
    "next_url",
    [
        "https://attacker.example/v1.0/me/messages?page=2",
        f"{BASE}/users/unapproved/messages?page=2",
        "https://graph.microsoft.com@attacker.example/v1.0/me/messages?page=2",
    ],
)
def test_unsafe_pagination_never_sends_a_token(next_url):
    def handler(request):
        assert request.url.host == "graph.microsoft.com"
        assert "unapproved" not in str(request.url)
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=PROFILE)
        return httpx.Response(200, json={"value": [], "@odata.nextLink": next_url})

    with pytest.raises(ValueError):
        fetch_outlook_mail(context(handler))


def test_page_limit_fails_instead_of_returning_partial_data():
    def handler(request):
        return httpx.Response(
            200,
            json=PROFILE
            if request.url.path.endswith("/me")
            else {"value": [], "@odata.nextLink": f"{BASE}/me/messages?page=2"},
        )

    with pytest.raises(ValueError, match="page limit"):
        fetch_outlook_mail(context(handler, max_pages=1))


def test_calendar_scopes_participants_dates_and_pagination():
    def handler(request):
        assert request.method == "GET"
        if request.url.path.endswith("/me"):
            return httpx.Response(200, json=PROFILE)
        assert request.url.path == "/v1.0/me/calendars/calendar-id/calendarView"
        assert request.headers["prefer"] == 'outlook.timezone="UTC"'
        if "page=2" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "value": [
                        event(
                            id="offset",
                            start={
                                "dateTime": "2026-09-01T10:00:00+01:00",
                                "timeZone": "ignored-with-offset",
                            },
                        )
                    ]
                },
            )
        assert "startDateTime" in request.url.params
        assert "$select" not in request.url.params
        return httpx.Response(
            200,
            json={
                "value": [
                    event(),
                    event(id="future", lastModifiedDateTime="2026-08-27T00:00:00Z"),
                    event(id="cancelled", isCancelled=True),
                    event(id="other", attendees=[]),
                    event(
                        id="beyond", start={"dateTime": "2026-12-01T00:00:00", "timeZone": "UTC"}
                    ),
                ],
                "@odata.nextLink": f"{BASE}/me/calendars/calendar-id/calendarView?page=2",
            },
        )

    records = fetch_outlook_calendar(context(handler))
    assert len(records) == 2
    assert records[0].source == "calendar"
    assert records[0].scheduled_at == datetime(2026, 9, 1, 9, tzinfo=UTC)
    assert records[0].scheduled_at == records[1].scheduled_at
    assert records[0].occurred_at.year == 2025
    assert records[0].text.endswith("Discuss funding.")


def test_calendar_rejects_ambiguous_timezone():
    def handler(request):
        return httpx.Response(
            200,
            json=PROFILE
            if request.url.path.endswith("/me")
            else {
                "value": [
                    event(
                        start={
                            "dateTime": "2026-09-01T09:00:00",
                            "timeZone": "Pacific Standard Time",
                        }
                    )
                ]
            },
        )

    with pytest.raises(ValueError, match="UTC or an explicit offset"):
        fetch_outlook_calendar(context(handler))
