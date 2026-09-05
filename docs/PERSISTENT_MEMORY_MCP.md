# Persistent memory and live MCP

The data-backed graph now has a durable runtime and an actual MCP server. This is a local,
single-Relationship-Manager demo, not an integration with real Gmail or Teams accounts.
The implementation uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/tree/v1.x)
and [LangGraph checkpoint persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

## Run

Install the locked dependencies with `uv sync --locked --all-groups`.

In terminal 1, start the read-only server:

```bash
uv run python -m app.mcp.server --transport streamable-http
```

It listens at `http://127.0.0.1:8001/mcp`, with only `CL-0003` enabled. Repeat
`--client-id CL-0003 --client-id CL-0012` to explicitly enable more Clients.
The default transport is `stdio`, for MCP hosts that launch subprocesses:

```bash
uv run python -m app.mcp.server
```

In terminal 2, run the graph through the live server:

```bash
uv run python -m scripts.run_client_flow --mcp-url http://127.0.0.1:8001/mcp --output data/generated/client-flow/live-mcp.json
```

Omit `--mcp-url` for the deterministic, network-free path. Both modes use the same loaders,
record contracts, retrieval algorithm, Evidence Gate, and persistent graph state. No API key is
needed. Stop the server with Ctrl-C.

## What persists

`--memory-dir` defaults to the Git-ignored `data/generated/memory/`. Pass the same directory
to the server, interaction importer, and graph for one demo session.

| Storage | Contents |
| --- | --- |
| `records.sqlite3` | Immutable versions of added interactions and idempotent Review Decisions |
| `checkpoints.sqlite3` | Client-bound graph state, cited retrieval index, pack history, last approval, and review interrupts |
| Original `data/` files | Read-only source dataset; loaded afresh so source changes are detected |

The CLI uses thread `sample:<client_id>`. Repeating it after restarting the process produces
`no_material_change` for unchanged inputs. A new interaction produces `incremental_update`
with `change_kind: memory`; changed financial source content is recomputed. Nothing auto-approves.
The pure `build_data_flow()` test helper still defaults to in-memory checkpoints; use
`app.agents.runtime.persistent_data_flow()` for durable application integration.

## Add and recall an interaction

Import the explicitly labelled synthetic example; original source files are untouched:

```bash
uv run python -m scripts.manage_memory import tests/fixtures/member_2/interaction.local.json
uv run python -m scripts.run_client_flow --mcp-url http://127.0.0.1:8001/mcp --output data/generated/client-flow/updated-mcp.json
uv run python -m scripts.manage_memory history CL-0003 notes:demo-meeting
```

Importing identical content twice is harmless. Corrections need a new `version` and preserve the
old version; changing content under an existing version is rejected. Use a new ID for a new
interaction. The importer accepts one normalized `CommunicationRecord` JSON, not arbitrary emails
or automatic account synchronization. It never rewrites original dataset notes.

The graph combines original notes and stored interactions, retrieves exact spans using its existing
topic-filtered TF-IDF index, and carries stable citation IDs into the Client Memory Card. MCP also
exposes `search_client_memory` for direct recall. No neural/vector service is required.

## Review across restarts

Inspect the output and copy its exact `pack_version` into a decision file:

```json
{
  "client_id": "CL-0003",
  "pack_version": "COPY_THE_CURRENT_PACK_VERSION",
  "action": "Approve"
}
```

Submit only after an RM has reviewed the pack:

```bash
uv run python -m scripts.run_client_flow --review-file /path/to/decision.json --output data/generated/client-flow/reviewed.json
```

Use the same `--mcp-url`, `--memory-dir`, `--client-id`, and `--as-of` as the original run.
The CLI refreshes inputs before resuming, rejecting stale decisions if data or memory changed.
`Edit`, `Reject`, and `Flag` retain the existing graph rules. The shared review node also rechecks
sources after its interrupt resumes, so direct `graph.invoke(Command(...))` callers cannot bypass
freshness checks. Changed or unavailable inputs route back through context without accepting the
decision; inspect the refreshed result and submit a new version-bound decision.

## MCP boundary and limitations

Three read-only tools are advertised through the actual MCP protocol:

- `get_client_bundle(client_id, as_of)`: deterministic Facts, Signals, and Evidence.
- `get_client_context(client_id, as_of)`: original RM notes plus stored interactions.
- `search_client_memory(client_id, as_of, query, topic, limit)`: exact cited spans and scores.

The graph uses the first two through an SDK client with initialization, structured tool results,
bounded timeouts, and fail-closed errors. Retrieval details persist in the graph trace. The third
is available to MCP hosts; internal agents continue using their local index over the fetched records.
Transport is recorded as `Live`; record availability remains `Cached`. Gmail, Teams and calendar
remain `Not connected` unless explicitly imported records exist, in which case those records are
still only `Cached`. Local imports do not prove an account connection.

The server binds only to loopback and uses the SDK's Host/Origin protection. The graph client
allows only `http://127.0.0.1:PORT/mcp`, ignores environment proxies, and follows no redirects.
This is not user authentication: local processes can read the enabled synthetic Client data.
Do not tunnel it, expose it remotely, or load real banking data without authentication and access
controls. Treat database files and graph outputs as sensitive; no encryption or retention policy
is implemented.

Run one graph writer at a time per memory directory, and do not import/correct records during a
review submission. SQLite transactions protect individual writes, not a multi-process workflow.
Stored corrections use latest-known versions eligible by `occurred_at`, not a historical
"what did we know at ingestion time" reconstruction. The local history command intentionally
shows all versions, including future-dated ones; it is not exposed as an as-of MCP tool.
Deletion/tombstones, background polling, external OAuth connectors, neural embeddings, and the
frontend Meeting Brief API remain separate work. Trigger a refresh by rerunning the CLI.

## Checks

```bash
uv run pytest tests/test_persistent_memory.py tests/test_mcp_runtime.py
```

Tests start and stop actual stdio/loopback HTTP servers, call tools through the SDK, execute the
data-backed graph, reopen SQLite checkpoints, add an interaction, reject a stale approval, and
confirm that a stopped MCP server blocks publication. No external service or model is contacted.
