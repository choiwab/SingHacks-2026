"""Validated demo scopes and the read-only HTTP boundary shared by external connectors."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import Field, field_validator, model_validator

from app.agents.contracts import fingerprint
from app.mcp.records import CommunicationRecord, Source
from app.pipeline.agent_inputs import _note_topics
from app.pipeline.schemas import ContractModel


def email_address(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}", value):
        raise ValueError("Expected an exact email address")
    return value


class ClientScope(ContractModel):
    emails: list[str] = Field(min_length=1, max_length=10)
    gmail: bool = False
    outlook_mail: bool = False
    google_calendar_ids: list[str] = Field(default_factory=list, max_length=10)
    outlook_calendar_ids: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("emails")
    @classmethod
    def valid_emails(cls, values: list[str]) -> list[str]:
        return sorted({email_address(value) for value in values})

    @field_validator("google_calendar_ids", "outlook_calendar_ids")
    @classmethod
    def valid_ids(cls, values: list[str]) -> list[str]:
        if any(not v.strip() or len(v) > 512 or any(ord(c) < 32 for c in v) for v in values):
            raise ValueError("Invalid provider resource ID")
        return sorted(set(values))


class ConnectorSettings(ContractModel):
    demo_accounts_only: bool
    google_account_email: str | None = None
    microsoft_account_id: str | None = None
    clients: dict[str, ClientScope]
    lookback_days: int = Field(default=180, ge=1, le=365)
    future_days: int = Field(default=30, ge=1, le=90)
    max_pages: int = Field(default=10, ge=1, le=20)

    @model_validator(mode="after")
    def valid_scope(self):
        if not self.demo_accounts_only or not self.clients:
            raise ValueError(
                "Explicit synthetic demo-account confirmation and client scopes required"
            )
        if self.google_account_email:
            self.google_account_email = email_address(self.google_account_email)
        if self.microsoft_account_id and not re.fullmatch(
            r"[a-fA-F0-9-]{36}", self.microsoft_account_id
        ):
            raise ValueError("Microsoft account ID must be a Graph user object ID")
        seen_emails: set[str] = set()
        for client, scope in self.clients.items():
            if not re.fullmatch(r"CL-\d{4}", client):
                raise ValueError("Invalid Client ID")
            if seen_emails.intersection(scope.emails):
                raise ValueError("Clients cannot share email identities")
            seen_emails.update(scope.emails)
            if self.google_account_email in scope.emails:
                raise ValueError("RM and client email identities must be distinct")
            if (scope.gmail or scope.google_calendar_ids) and not self.google_account_email:
                raise ValueError("Google connectors require an expected RM account email")
            if (scope.outlook_mail or scope.outlook_calendar_ids) and not self.microsoft_account_id:
                raise ValueError("Microsoft connectors require an expected RM Graph account ID")
        return self


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(value: str) -> str:
    parser = _PlainText()
    parser.feed(value)
    return "".join(parser.parts).strip()


def timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Provider timestamps must have a timezone")
    return parsed.astimezone(UTC)


@dataclass
class ReadContext:
    settings: ConnectorSettings
    client_id: str
    scope: ClientScope
    as_of: datetime
    retrieved_at: datetime
    http: httpx.Client
    token: str
    provider: str

    @property
    def since(self) -> datetime:
        return self.as_of - timedelta(days=self.settings.lookback_days)

    @property
    def until(self) -> datetime:
        return self.as_of + timedelta(days=self.settings.future_days)

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        target = urlsplit(url)
        allowed = (
            {"gmail.googleapis.com", "www.googleapis.com"}
            if self.provider == "google"
            else {"graph.microsoft.com"}
        )
        if (
            target.scheme != "https"
            or target.hostname not in allowed
            or target.port not in {None, 443}
            or target.username
            or target.password
            or target.fragment
        ):
            raise ValueError("Provider URL is outside the allowed origin")
        response = self.http.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {self.token}", "Prefer": 'outlook.timezone="UTC"'},
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Invalid provider response")
        return result

    def record(
        self,
        *,
        source: Source,
        native_id: str,
        occurred_at: datetime,
        text: str,
        participants: list[str],
        based_on: str,
        scheduled_at: datetime | None = None,
    ) -> CommunicationRecord:
        # IDs retain provider/account/client scope, preventing collisions across imports.
        account = (
            self.settings.google_account_email
            if self.provider == "google"
            else self.settings.microsoft_account_id
        )
        identity = fingerprint([self.provider, account, self.client_id, native_id])[:24]
        content = {
            "text": text,
            "participants": sorted(set(participants)),
            "occurred_at": occurred_at.isoformat(),
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
        }
        return CommunicationRecord(
            id=f"{source}:{self.provider}:{identity}",
            client_id=self.client_id,
            source=source,
            version=fingerprint(content),
            occurred_at=occurred_at,
            retrieved_at=self.retrieved_at,
            scheduled_at=scheduled_at,
            participants=content["participants"],
            text=text,
            topics=_note_topics(text),
            provenance="recorded_live",
            availability="Live",
            based_on=[based_on],
        )
