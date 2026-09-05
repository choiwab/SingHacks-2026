"""Read-only Microsoft Graph connectors for explicitly mapped demo resources."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, unquote, urlsplit

from app.mcp.external_common import ReadContext, plain_text, timestamp
from app.mcp.records import CommunicationRecord

GRAPH = "https://graph.microsoft.com/v1.0"


def _verify_account(ctx: ReadContext) -> dict[str, Any]:
    account = ctx.get(f"{GRAPH}/me", {"$select": "id,mail,userPrincipalName"})
    expected = ctx.settings.microsoft_account_id
    if not expected or str(account.get("id", "")).lower() != expected.lower():
        raise ValueError("Microsoft token belongs to a different RM account")
    return account


def _pages(
    ctx: ReadContext, url: str, params: dict[str, Any] | None = None
) -> Iterator[dict[str, Any]]:
    resource = unquote(urlsplit(url).path)
    for _ in range(ctx.settings.max_pages):
        page = ctx.get(url, params)
        entries = page.get("value")
        if not isinstance(entries, list) or any(not isinstance(v, dict) for v in entries):
            raise ValueError("Invalid Microsoft collection response")
        yield from entries
        next_url = page.get("@odata.nextLink")
        if not next_url:
            return
        if not isinstance(next_url, str) or unquote(urlsplit(next_url).path) != resource:
            raise ValueError("Microsoft pagination escaped the approved resource")
        # ReadContext also checks HTTPS, host, port and credentials before sending a token.
        url, params = next_url, None
    raise ValueError("Microsoft page limit reached; refusing incomplete retrieval")


def _effective_time(item: dict[str, Any]) -> datetime:
    dates = [timestamp(item["createdDateTime"])]
    dates.extend(timestamp(item[key]) for key in ("lastModifiedDateTime",) if item.get(key))
    return max(dates)


def _body(item: dict[str, Any]) -> str:
    body = item.get("body") or {}
    content = body.get("content", "")
    return plain_text(content) if body.get("contentType", "").lower() == "html" else content


def _mail_participants(message: dict[str, Any]) -> list[str]:
    people = [
        message.get("from") or {},
        *(message.get("toRecipients") or []),
        *(message.get("ccRecipients") or []),
        *(message.get("bccRecipients") or []),
    ]
    return sorted(
        {str((p.get("emailAddress") or {}).get("address", "")).strip().lower() for p in people}
        - {""}
    )


def _mail_time(message: dict[str, Any]) -> datetime:
    return max(
        timestamp(message[key])
        for key in ("receivedDateTime", "sentDateTime", "lastModifiedDateTime")
        if message.get(key)
    )


def fetch_outlook_mail(ctx: ReadContext) -> list[CommunicationRecord]:
    """Read matched Client/RM mail, fetching bodies only after exact header scoping."""
    account = _verify_account(ctx)
    rm_emails = {
        str(account.get(key) or "").strip().lower() for key in ("mail", "userPrincipalName")
    } - {""}
    if not rm_emails:
        raise ValueError("Microsoft account has no verifiable email identity")
    if rm_emails.intersection(ctx.scope.emails):
        raise ValueError("RM and client email identities must be distinct")
    records = []
    resource = f"{GRAPH}/me/messages"
    fields = (
        "id,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,"
        "sentDateTime,lastModifiedDateTime,isDraft"
    )
    params = {
        "$top": 100,
        "$select": fields,
        "$orderby": "receivedDateTime desc",
        "$filter": (
            f"receivedDateTime ge {ctx.since.isoformat()} "
            f"and receivedDateTime le {ctx.as_of.isoformat()}"
        ),
    }
    # ponytail: bounded mailbox metadata scan; provider-side client search if demo volume grows.
    for metadata in _pages(ctx, resource, params):
        participants = set(_mail_participants(metadata))
        if (
            metadata.get("isDraft")
            or not participants.intersection(ctx.scope.emails)
            or not participants.intersection(rm_emails)
            or not ctx.since <= _mail_time(metadata) <= ctx.as_of
        ):
            continue
        message_id = metadata["id"]
        url = f"{resource}/{quote(message_id, safe='')}"
        message = ctx.get(url, {"$select": f"{fields},subject,body"})
        if message.get("id") != message_id:
            raise ValueError("Microsoft returned an unexpected message ID")
        participants = set(_mail_participants(message))
        occurred_at = _mail_time(message)
        # Recheck after the body fetch: a message may have changed since the listing.
        if (
            message.get("isDraft")
            or not participants.intersection(ctx.scope.emails)
            or not participants.intersection(rm_emails)
            or not ctx.since <= occurred_at <= ctx.as_of
        ):
            continue
        sender = str(((message.get("from") or {}).get("emailAddress") or {}).get("address", ""))
        text = (
            f"From: {sender}\nSubject: {message.get('subject') or '(no subject)'}\n"
            f"{_body(message).strip()}"
        )
        records.append(
            ctx.record(
                source="outlook",
                native_id=f"message:{message_id}",
                occurred_at=occurred_at,
                text=text,
                participants=sorted(participants),
                based_on=url,
            )
        )
    return records


def _calendar_time(value: dict[str, str]) -> datetime:
    parsed = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if value.get("timeZone") not in {"UTC", "Etc/UTC"}:
            raise ValueError("Microsoft calendar must return UTC or an explicit offset")
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def fetch_outlook_calendar(ctx: ReadContext) -> list[CommunicationRecord]:
    """Read scoped calendar instances known by as-of, including upcoming meetings."""
    _verify_account(ctx)
    records = []
    for calendar_id in ctx.scope.outlook_calendar_ids:
        resource = f"{GRAPH}/me/calendars/{quote(calendar_id, safe='')}"
        params = {
            "startDateTime": ctx.since.isoformat(),
            "endDateTime": ctx.until.isoformat(),
            "$top": 100,
        }
        for event in _pages(ctx, f"{resource}/calendarView", params):
            if event.get("isCancelled"):
                continue
            people = [event.get("organizer") or {}, *(event.get("attendees") or [])]
            participants = sorted(
                {
                    str((p.get("emailAddress") or {}).get("address", "")).strip().lower()
                    for p in people
                }
                - {""}
            )
            if not set(participants).intersection(ctx.scope.emails):
                continue
            occurred_at = _effective_time(event)
            scheduled_at = _calendar_time(event["start"])
            # Calendar lookback applies to scheduled dates, not creation: a long-booked
            # upcoming appointment is still relevant, but future edits cannot leak in.
            if occurred_at > ctx.as_of or not ctx.since <= scheduled_at <= ctx.until:
                continue
            event_id = event["id"]
            text = "\n".join(
                part
                for part in [
                    f"Meeting: {event.get('subject') or '(untitled)'}",
                    f"Scheduled: {scheduled_at.isoformat()}",
                    _body(event).strip(),
                ]
                if part
            )
            records.append(
                ctx.record(
                    source="calendar",
                    native_id=f"calendar:{calendar_id}:event:{event_id}",
                    occurred_at=occurred_at,
                    text=text,
                    participants=participants,
                    based_on=f"{resource}/events/{quote(event_id, safe='')}",
                    scheduled_at=scheduled_at,
                )
            )
    return records
