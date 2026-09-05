"""Google contracts exercised against HTTP-shaped fixtures, without credentials."""

import base64
from copy import deepcopy
from datetime import UTC, datetime

import httpx
import pytest

from app.mcp.external_common import ConnectorSettings, ReadContext
from app.mcp.google_connectors import fetch_gmail, fetch_google_calendar

AS_OF = datetime(2026, 8, 26, 23, 59, tzinfo=UTC)


def context(handler, *, max_pages=3, enabled=True):
    settings = ConnectorSettings.model_validate(
        {
            "demo_accounts_only": True,
            "google_account_email": "rm@example.com",
            "max_pages": max_pages,
            "clients": {
                "CL-0003": {
                    "emails": ["client@example.com"],
                    "gmail": enabled,
                    "google_calendar_ids": ["demo@example.com"] if enabled else [],
                }
            },
        }
    )
    return ReadContext(
        settings,
        "CL-0003",
        settings.clients["CL-0003"],
        AS_OF,
        AS_OF,
        httpx.Client(transport=httpx.MockTransport(handler)),
        "test-token",
        "google",
    )


def message(native_id="m1", recipient="client@example.com"):
    body = b"I would like a funding summary."
    return {
        "id": native_id,
        "internalDate": str(int(AS_OF.timestamp() * 1000)),
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "RM <rm@example.com>"},
                {"name": "To", "value": f"Client <{recipient}>"},
                {"name": "Subject", "value": "Meeting preparation"},
            ],
            "body": {"data": base64.urlsafe_b64encode(body).decode(), "size": len(body)},
        },
    }


def event(native_id="e1", **changes):
    return {
        "id": native_id,
        "status": "confirmed",
        "summary": "Funding discussion",
        "created": "2026-08-20T10:00:00Z",
        "updated": "2026-08-25T10:00:00Z",
        "start": {"dateTime": "2026-09-01T10:00:00+08:00"},
        "end": {"dateTime": "2026-09-01T11:00:00+08:00"},
        "attendees": [{"email": "client@example.com"}],
        "organizer": {"email": "rm@example.com"},
        "description": "<p>Please discuss funding.</p><script>hidden()</script>",
        **changes,
    }


def test_gmail_paginates_checks_participants_dates_and_drafts():
    calls = []

    def handler(request):
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer test-token"
        calls.append(request)
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "rm@example.com"})
        if request.url.path.endswith("/messages"):
            query = request.url.params["q"]
            assert (
                'from:"client@example.com"' in query
                and "before:" in query
                and "-in:drafts" in query
            )
            if "pageToken" in request.url.params:
                assert request.url.params["pageToken"] == "next"
                return httpx.Response(
                    200, json={"messages": [{"id": "m1"}, {"id": "future"}, {"id": "draft"}]}
                )
            return httpx.Response(
                200, json={"messages": [{"id": "m1"}, {"id": "other"}], "nextPageToken": "next"}
            )
        native_id = request.url.path.rsplit("/", 1)[-1]
        item = message(
            native_id, "notclient@example.com" if native_id == "other" else "client@example.com"
        )
        if native_id == "future":
            item["internalDate"] = str(int(AS_OF.timestamp() * 1000) + 1)
        if native_id == "draft":
            item["labelIds"] = ["DRAFT"]
        return httpx.Response(200, json=item)

    records = fetch_gmail(context(handler))
    assert len(records) == 1
    record = records[0]
    assert record.source == "gmail" and record.availability == "Live"
    assert record.provenance == "recorded_live" and record.client_id == "CL-0003"
    assert record.occurred_at == AS_OF
    assert "funding summary" in record.text
    assert record.based_on == ["gmail:message:m1"]
    assert sum(request.url.path.endswith("/messages/m1") for request in calls) == 1


@pytest.mark.parametrize("fetch", [fetch_gmail, fetch_google_calendar])
def test_google_wrong_account_fails_before_reading_records(fetch):
    def handler(request):
        assert request.url.path.endswith("/profile")
        return httpx.Response(200, json={"emailAddress": "wrong@example.com"})

    with pytest.raises(ValueError, match="designated demo RM"):
        fetch(context(handler))


@pytest.mark.parametrize("fetch,key", [(fetch_gmail, "messages"), (fetch_google_calendar, "items")])
def test_google_page_limit_never_returns_partial_snapshot(fetch, key):
    def handler(request):
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "rm@example.com"})
        return httpx.Response(200, json={key: [], "nextPageToken": "again"})

    with pytest.raises(ValueError, match="partial refresh"):
        fetch(context(handler, max_pages=1))


def test_gmail_multipart_charset_html_and_attachments():
    item = message()
    original = deepcopy(item["payload"])
    original["headers"] = [{"name": "Content-Type", "value": "text/plain; charset=iso-8859-1"}]
    data = "préférences".encode("iso-8859-1")
    original["body"] = {
        "data": base64.urlsafe_b64encode(data).decode().rstrip("="),
        "size": len(data),
    }
    item["payload"].update(
        {
            "mimeType": "multipart/mixed",
            "body": {},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [original, {"mimeType": "text/html", "body": {"data": "invalid"}}],
                },
                {
                    "mimeType": "application/pdf",
                    "filename": "statement.pdf",
                    "body": {"attachmentId": "never-fetch"},
                },
                {
                    "mimeType": "text/html",
                    "body": {
                        "data": base64.urlsafe_b64encode(
                            b"<b>Plain</b><script>secret</script>"
                        ).decode()
                    },
                },
            ],
        }
    )

    def handler(request):
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "rm@example.com"})
        if request.url.path.endswith("/messages"):
            return httpx.Response(200, json={"messages": [{"id": "m1"}]})
        assert request.url.path.endswith("/messages/m1")
        return httpx.Response(200, json=item)

    text = fetch_gmail(context(handler))[0].text
    assert "préférences" in text and "Plain" in text and "Attachment not retrieved" in text
    assert "secret" not in text and "<b>" not in text
    item["payload"]["parts"] = [original]
    original["body"]["size"] += 1
    with pytest.raises(ValueError, match="Incomplete Gmail body"):
        fetch_gmail(context(handler))


def test_google_calendar_expanded_instances_all_day_future_edits_and_client_scope():
    events = [
        event(),
        event("all-day", start={"date": "2026-09-02"}, end={"date": "2026-09-03"}),
        event("edited-future", updated="2026-08-27T00:00:00Z"),
        event("cancelled", status="cancelled"),
        event("other", attendees=[{"email": "notclient@example.com"}]),
        event(
            "outside",
            start={"dateTime": "2027-01-01T00:00:00Z"},
            end={"dateTime": "2027-01-02T00:00:00Z"},
        ),
    ]

    def handler(request):
        assert request.method == "GET"
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "rm@example.com"})
        assert request.url.path == "/calendar/v3/calendars/demo@example.com/events"
        assert request.url.params["singleEvents"] == "true"
        assert "timeMin" in request.url.params and "timeMax" in request.url.params
        if request.url.params.get("pageToken") == "page2":
            return httpx.Response(200, json={"timeZone": "Asia/Singapore", "items": events[1:]})
        return httpx.Response(
            200, json={"timeZone": "Asia/Singapore", "items": events[:1], "nextPageToken": "page2"}
        )

    records = fetch_google_calendar(context(handler))
    assert len(records) == 2
    assert all(record.source == "calendar" and record.availability == "Live" for record in records)
    timed = next(record for record in records if "All-day" not in record.text)
    assert timed.scheduled_at == datetime(2026, 9, 1, 2, tzinfo=UTC)
    assert timed.occurred_at == datetime(2026, 8, 25, 10, tzinfo=UTC)
    assert "hidden" not in timed.text
    all_day = next(record for record in records if "All-day" in record.text)
    assert all_day.scheduled_at == datetime(2026, 9, 1, 16, tzinfo=UTC)


def test_google_disabled_sources_do_not_connect():
    def handler(request):
        pytest.fail("Disabled sources must not connect")

    ctx = context(handler, enabled=False)
    assert fetch_gmail(ctx) == [] and fetch_google_calendar(ctx) == []
