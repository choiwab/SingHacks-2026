"""Read-only Gmail and Google Calendar adapters for explicitly scoped demo accounts."""

import base64
import binascii
from datetime import UTC, datetime, time
from email.header import decode_header, make_header
from email.message import Message
from email.utils import getaddresses
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from app.mcp.external_common import ReadContext, plain_text, timestamp
from app.mcp.records import CommunicationRecord

GMAIL = "https://gmail.googleapis.com/gmail/v1/users/me"
CALENDAR = "https://www.googleapis.com/calendar/v3/calendars"


def _check_account(ctx: ReadContext) -> None:
    profile = ctx.get(f"{GMAIL}/profile")
    if profile.get("emailAddress", "").lower() != ctx.settings.google_account_email:
        raise ValueError("Google account does not match the designated demo RM")


def _items(page: dict, key: str) -> list[dict[str, Any]]:
    items = page.get(key, [])
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("Malformed Google result list")
    return items


def _headers(part: dict) -> Message:
    message = Message()
    for header in _items(part, "headers"):
        if not isinstance(header.get("name"), str) or not isinstance(header.get("value"), str):
            raise ValueError("Malformed Gmail header")
        message[header["name"]] = header["value"]
    return message


def _body(part: dict) -> str:
    headers = _headers(part)
    if part.get("filename") or headers.get_content_disposition() == "attachment":
        return "[Attachment not retrieved.]"
    parts = _items(part, "parts")
    if parts:
        # Prefer the plain alternative rather than duplicating HTML and plain bodies.
        if part.get("mimeType") == "multipart/alternative":
            selected = next((p for p in parts if p.get("mimeType") == "text/plain"), parts[-1])
            return _body(selected)
        return "\n".join(filter(None, (_body(p) for p in parts)))
    mime = part.get("mimeType", "")
    if mime not in {"text/plain", "text/html"}:
        return "[Non-text content not retrieved.]"
    body = part.get("body", {})
    if not isinstance(body, dict):
        raise ValueError("Malformed Gmail body")
    if body.get("attachmentId"):
        raise ValueError("Gmail text requires an attachment fetch; complete body unavailable")
    data = body.get("data", "")
    if not isinstance(data, str):
        raise ValueError("Malformed Gmail body data")
    try:
        decoded = base64.b64decode(data + "=" * (-len(data) % 4), altchars=b"-_", validate=True)
        if body.get("size", len(decoded)) != len(decoded):
            raise ValueError("Incomplete Gmail body")
        text = decoded.decode(headers.get_content_charset() or "utf-8")
    except (binascii.Error, LookupError, UnicodeError) as exc:
        raise ValueError("Cannot decode complete Gmail text") from exc
    return plain_text(text) if mime == "text/html" else text.strip()


def fetch_gmail(ctx: ReadContext) -> list[CommunicationRecord]:
    """Fetch scoped messages, never drafts, attachments, or an entire mailbox."""
    if not ctx.scope.gmail:
        return []
    _check_account(ctx)
    query = (
        "{"
        + " ".join(
            f'{field}:"{address}"' for address in ctx.scope.emails for field in ("from", "to", "cc")
        )
        + "}"
    )
    params: dict[str, Any] = {
        "q": (
            f"{query} after:{int(ctx.since.timestamp()) - 1} "
            f"before:{int(ctx.as_of.timestamp()) + 1} -in:drafts"
        ),
        "maxResults": 100,
        "includeSpamTrash": "false",
    }
    records: dict[str, CommunicationRecord] = {}
    seen: set[str] = set()
    for _ in range(ctx.settings.max_pages):
        page = ctx.get(f"{GMAIL}/messages", params)
        for item in _items(page, "messages"):
            native_id = item.get("id")
            if not isinstance(native_id, str) or not native_id:
                raise ValueError("Gmail message ID missing")
            if native_id in seen:
                continue
            seen.add(native_id)
            message = ctx.get(f"{GMAIL}/messages/{quote(native_id, safe='')}", {"format": "full"})
            if message.get("id") != native_id:
                raise ValueError("Gmail returned a mismatched message")
            if "DRAFT" in message.get("labelIds", []):
                continue
            try:
                occurred_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000, UTC)
                payload = message["payload"]
            except (KeyError, ValueError, TypeError, OverflowError) as exc:
                raise ValueError("Invalid Gmail message date or payload") from exc
            if not isinstance(payload, dict):
                raise ValueError("Invalid Gmail payload")
            if not ctx.since <= occurred_at <= ctx.as_of:
                continue
            headers = _headers(payload)
            participants = sorted(
                {
                    address.lower()
                    for _, address in getaddresses(
                        [
                            value
                            for field in ("from", "to", "cc")
                            for value in headers.get_all(field, [])
                        ]
                    )
                    if address
                }
            )
            if not set(participants).intersection(ctx.scope.emails):
                continue
            subject = str(make_header(decode_header(headers.get("subject", "(No subject)"))))
            body = _body(payload)
            records[native_id] = ctx.record(
                source="gmail",
                native_id=native_id,
                occurred_at=occurred_at,
                text=f"Subject: {subject}\n{body or '[Empty message body.]'}",
                participants=participants,
                based_on=f"gmail:message:{native_id}",
            )
        token = page.get("nextPageToken")
        if not token:
            return sorted(records.values(), key=lambda record: (record.occurred_at, record.id))
        if not isinstance(token, str):
            raise ValueError("Malformed Gmail page token")
        params["pageToken"] = token
    raise ValueError("Gmail page limit reached; refusing a partial refresh")


def _event_time(value: dict, calendar_zone: str | None) -> datetime:
    if not isinstance(value, dict):
        raise ValueError("Invalid Google Calendar event time")
    if value.get("dateTime"):
        raw = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
        if raw.tzinfo is not None:
            return raw.astimezone(UTC)
        zone = value.get("timeZone")
    elif value.get("date"):
        raw = datetime.combine(datetime.strptime(value["date"], "%Y-%m-%d").date(), time.min)
        zone = value.get("timeZone") or calendar_zone
    else:
        raise ValueError("Missing Google Calendar start/end time")
    if not zone:
        raise ValueError("Calendar event lacks a timezone")
    try:
        return raw.replace(tzinfo=ZoneInfo(zone)).astimezone(UTC)
    except (KeyError, TypeError) as exc:
        raise ValueError("Invalid Google Calendar timezone") from exc


def fetch_google_calendar(ctx: ReadContext) -> list[CommunicationRecord]:
    """Read allowlisted calendars, filtering participants and future edits locally."""
    if not ctx.scope.google_calendar_ids:
        return []
    _check_account(ctx)
    records: dict[str, CommunicationRecord] = {}
    for calendar_id in ctx.scope.google_calendar_ids:
        params: dict[str, Any] = {
            "timeMin": ctx.since.isoformat(),
            "timeMax": ctx.until.isoformat(),
            "singleEvents": "true",
            "showDeleted": "false",
            "maxResults": 250,
        }
        for _ in range(ctx.settings.max_pages):
            page = ctx.get(f"{CALENDAR}/{quote(calendar_id, safe='')}/events", params)
            for event in _items(page, "items"):
                if event.get("status") == "cancelled":
                    continue
                if event.get("attendeesOmitted"):
                    raise ValueError(
                        "Google Calendar omitted attendees; client scope cannot be verified"
                    )
                people = _items(event, "attendees") + [event.get("organizer", {})]
                if any(not isinstance(person, dict) for person in people):
                    raise ValueError("Malformed calendar participants")
                participants = sorted(
                    {person["email"].lower() for person in people if person.get("email")}
                )
                if not set(participants).intersection(ctx.scope.emails):
                    continue
                try:
                    occurred_at = max(timestamp(event["created"]), timestamp(event["updated"]))
                except (KeyError, TypeError) as exc:
                    raise ValueError("Calendar creation/update timestamp missing") from exc
                if occurred_at > ctx.as_of:
                    continue
                start = _event_time(event.get("start", {}), page.get("timeZone"))
                end = _event_time(event.get("end", {}), page.get("timeZone"))
                if end <= start:
                    raise ValueError("Calendar event ends before it starts")
                if start >= ctx.until or end <= ctx.since:
                    continue
                native_id = event.get("id")
                if not isinstance(native_id, str) or not native_id:
                    raise ValueError("Google Calendar event ID missing")
                # Recurring instances retain their provider instance ID, not the series ID.
                key = f"{calendar_id}:{native_id}"
                text = "\n".join(
                    filter(
                        None,
                        [
                            f"Meeting: {event.get('summary', '(No title)')}",
                            f"Scheduled: {start.isoformat()} to {end.isoformat()}",
                            "All-day event." if "date" in event.get("start", {}) else "",
                            plain_text(event.get("description", "")),
                            f"Location: {event['location']}" if event.get("location") else "",
                        ],
                    )
                )
                record = ctx.record(
                    source="calendar",
                    native_id=key,
                    occurred_at=occurred_at,
                    text=text,
                    participants=participants,
                    scheduled_at=start,
                    based_on=f"google:calendar:{calendar_id}:event:{native_id}",
                )
                if key in records and records[key].version != record.version:
                    raise ValueError("Calendar changed during pagination; retry the refresh")
                records[key] = record
            token = page.get("nextPageToken")
            if not token:
                break
            if not isinstance(token, str):
                raise ValueError("Malformed Google Calendar page token")
            params["pageToken"] = token
        else:
            raise ValueError("Google Calendar page limit reached; refusing a partial refresh")
    return sorted(records.values(), key=lambda record: (record.occurred_at, record.id))
