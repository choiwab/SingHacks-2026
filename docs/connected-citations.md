# Connected citation projection

`GET /api/app` returns dataset Evidence in `evidence` and cited Connected Records in
`connected_evidence`. Connector provenance is never represented as a fabricated CSV row.

Persist a brief's `connected_context` as the Member 2 envelope containing `records`, `sources`,
and `retrieval_log`. Existing runs with a records list remain readable. A direct record citation
uses its exact `id`; its `connected_evidence` value is the original persisted record, unchanged.
Generated claims can carry references in `citations`, `record_ids`, or `record_id` fields.

For indexed citations, also persist `memory_index`, exactly as `MemoryIndex.snapshot()` returns it:

```json
{
  "client_id": "CL-0003",
  "as_of": "2026-08-26T23:59:59+00:00",
  "record_versions": {"gmail:1": "content-fingerprint"},
  "chunks": {
    "gmail:1#content-fing:0-5": {
      "id": "gmail:1#content-fing:0-5",
      "record_id": "gmail:1",
      "start": 0,
      "end": 5,
      "text": "Hello",
      "topics": ["communication"],
      "occurred_at": "2026-08-20T00:00:00+00:00"
    }
  }
}
```

The projection looks up a chunk ID exactly in `chunks`. It requires the index and parent record
to belong to the current Client, the parent to exist in that brief's Connected Records, a cached
record version, and the chunk's text to equal the parent's `[start:end]` span. The resulting
`connected_evidence[chunk_id]` contains `chunk` (the original chunk), `record` (the complete
original parent, including source, record version, retrieval time, and availability), and
`record_version` (the index's content fingerprint). Only cited entries are returned.

Unknown or orphan chunk IDs remain unresolved and fail evidence loading. The projection never
splits an ID at `#` to guess its parent and never reconstructs missing chunks from parent text.
The index fingerprint and the parent's source version are preserved as distinct values.
