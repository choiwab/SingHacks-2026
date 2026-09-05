# Connect Google and Outlook

The app supports opt-in, read-only Gmail, Outlook Mail, Google Calendar and Outlook Calendar
connectors. Teams is deferred. These are application adapters behind the existing MCP server,
not plugins installed into a Codex session. The default judged path remains offline.

## Connection status: hosted tools versus the application

The provided Gmail and Google Calendar plugins were connected and tested inside Codex on
2026-09-05. Gmail account lookup, message search, and metadata reads passed. One explicitly
requested self-addressed test email was sent and read back successfully. Calendar listing and
a bounded primary-calendar event search passed; the search returned no events, so event-detail
retrieval and calendar writes were not tested. Outlook was unavailable in that session.

Those hosted connections do not expose reusable credentials to this repository or automatically
connect the standalone backend. No mailbox content, account tokens, or personal identifiers from
the tests are committed. The application adapters below remain opt-in and tested with mocked
provider responses; their own live account authorization and end-to-end provider test remain pending.
The custom OAuth setup was paused in favor of testing the hosted tools. The instructions below
are retained as an optional standalone deployment path, not prerequisites for using hosted tools.

## 1. Register the demo applications

Use dedicated accounts containing synthetic demo correspondence only. OAuth permissions cover
the authorized mailbox/calendars; client filtering in this app is not provider-enforced access
control. In particular, Outlook scans dated mailbox metadata before selecting client bodies,
and calendars return event details before client-attendee filtering. Do not use real banking data.

### Google

1. Enable Gmail API and Google Calendar API in your Google Cloud project.
2. Configure OAuth consent and permit the designated demo user, including the test-user list
   when using an External app in Testing mode.
3. Create a **Desktop app** OAuth client and save its downloaded JSON as
   `.local/google-client.json`. Do not paste it into chat or commit it.
4. Add `GOOGLE_OAUTH_CLIENT_FILE=.local/google-client.json` to your existing `.env`.

The connector requests `gmail.readonly` and `calendar.events.readonly`. Calendar-only operation
still uses Gmail profile access to verify the configured RM identity. The desktop loopback
authorization flow follows [Google's setup guide](https://developers.google.com/workspace/gmail/api/quickstart/python).

### Microsoft

1. Register a single-tenant application in Microsoft Entra for a demo work/school account
   with an Outlook mailbox.
2. Enable **Allow public client flows** for device-code sign-in. No client secret is needed.
3. Add Microsoft Graph **delegated** permissions `User.Read`, `Mail.Read`, `Calendars.Read`.
   Obtain administrator consent if required by the tenant policy. Do not add Teams permissions.
4. Set `MICROSOFT_CLIENT_ID` and `MICROSOFT_TENANT_ID` in `.env` using the application and
   directory UUIDs. This initial implementation does not support personal Outlook.com accounts.

See [Microsoft's desktop-app configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration).
The RM account's user object ID is a separate value from the application/client ID.

## 2. Sign in explicitly

From the repository root:

```bash
uv sync --locked --all-groups
uv run --env-file .env python -m scripts.connect_accounts google
uv run --env-file .env python -m scripts.connect_accounts microsoft
```

Select the designated demo accounts. Google opens a browser; Microsoft prints a short-lived
device code to enter at Microsoft's sign-in page. Consent is required and is never automated.
Tokens are saved locally under Git-ignored `.local/connectors/`, with private file permissions.
The runtime can refresh tokens but never initiates sign-in. To revoke access, use the provider's
account/application permission controls. Local token and snapshot files also need explicit cleanup
when retiring the demo; deleting local tokens alone does not revoke provider consent.

## 3. Map clients and calendars

Copy [the placeholder configuration](examples/connectors.json) to `.local/connectors.json` and
replace its example values. Preserve the original source dataset.

- `google_account_email`: exact signed-in RM Gmail address.
- `microsoft_account_id`: exact signed-in RM user object ID from Entra, also returned by Graph
  `GET /v1.0/me`. This is not the OAuth application ID.
- `clients.CL-0003.emails`: exact addresses used by Margarethe's synthetic demo identity.
  RM and client identities must differ. Different clients cannot share mapped addresses.
- `google_calendar_ids`: `primary` or explicit IDs from the demo calendar's settings.
- `outlook_calendar_ids`: explicit calendar IDs from Graph `GET /v1.0/me/calendars`.
  The literal `primary` is not an Outlook calendar ID. Use an approved Graph client or Explorer
  with the demo account to inspect IDs; do not share access tokens.
- Disable either mail connector with `false`, or a calendar connector with an empty list.
  `demo_accounts_only: true` is an explicit operator assertion, not automated verification.

Both calendars appear under source `calendar`; record IDs and retrieval logs distinguish Google
and Microsoft. Outlook email has its own source, `outlook`, and is never labelled Gmail.

## 4. Fetch once, then run offline

```bash
uv run --env-file .env python -m scripts.sync_connectors --config .local/connectors.json --client-id CL-0003 --as-of 2026-08-26
uv run python -m scripts.run_client_flow --output data/generated/client-flow/connected-cached.json
```

The first command prints counts and availability, not message bodies or tokens. A successful read
is `Live` for that call and saved as `Cached` for later offline recall. Original RM notes are
preserved. The second command retrieves the saved records through the existing cited memory index
and still requires human review before approval.

**Dates matter:** the supplied portfolio demo is dated **2026-08-26**. Emails sent today are not
eligible for that historical run. Upcoming calendar events qualify only if they were already
created and last updated by the cutoff. Do not backdate messages or hide future edits. A current-date
end-to-end demo needs a deliberately updated, consistent portfolio dataset as well as current
communications. These connectors cannot reconstruct historical versions that providers no longer
return.

## 5. Read through the live MCP server

Alternatively, terminal 1:

```bash
uv run --env-file .env python -m app.mcp.server --transport streamable-http --connectors-config .local/connectors.json
```

Terminal 2:

```bash
uv run python -m scripts.run_client_flow --mcp-url http://127.0.0.1:8001/mcp --output data/generated/client-flow/connected-live.json
```

The existing `get_client_context` and `search_client_memory` tools now fetch enabled providers
and persist the successful snapshot. The same server without `--connectors-config` remains
offline. The graph's existing freshness checks also re-read context when resuming RM review.
Keep scopes small: the graph MCP client has a bounded timeout, and large mailbox scans may exceed
it. For a reliable judged run, use the explicit sync command followed by cached replay.

## Safety, completeness and current limits

- External data reads use GET only. No email sends, calendar writes, attachments, or Teams access.
- Exact client matching, account verification, date limits, pagination limits and source citations
  apply before records enter memory. Provider text is evidence, never agent instructions.
- A failed provider, malformed response or page-limit overflow fails the combined read. No partial
  snapshot is published and no silent cached fallback occurs in live mode. The last successful
  snapshot remains available through explicit offline mode.
- A successful replacement snapshot removes disappeared/cancelled records from active recall.
  Prior versions remain in local audit history. This is scoped snapshot replacement, not a
  provider webhook, delta-sync engine or general deletion API.
- Mail and calendars are bounded by configurable lookback/future windows. Outlook's
  [mailbox listing](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0)
  can include Deleted Items; no special folder exclusion is implemented. Drafts are excluded.
- The server stays loopback-only and unauthenticated for a single-RM synthetic demo. Do not tunnel
  it. Local tokens, SQLite memory and generated output are sensitive and are not encrypted at rest.
- This adds CLI/MCP account access, not dashboard sign-in buttons or a wired live calendar UI.
  Background polling, automatic meeting changes and production multi-user integration are deferred.

## Verification

```bash
uv run pytest tests/test_google_connectors.py tests/test_microsoft_connectors.py tests/test_connector_oauth.py tests/test_external_connectors.py tests/test_mcp_runtime.py
```

Provider tests use mocked responses, including client isolation, MIME/HTML handling, as-of filtering,
pagination refusal, credential refresh and atomic snapshots. Integration tests exercise cached
records through the data-backed graph and connector-enabled MCP handlers. Existing MCP runtime
tests use real local SDK transports, but no test authorizes or contacts an external account.
