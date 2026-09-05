# Frozen dashboard preview

`pnpm dev:preview` explicitly enables the historical dashboard while the replacement Demo View Model API is under development.
The page labels the data as a fixture preview and every review as a simulation.
The normal runtime never falls back to this fixture.

`dashboard.json` was exported from `build_monday_brief(Path("data"), as_of=date(2026, 8, 26))` at commit `0342d49e0f340c67f1c54807fa34521afb00b53a`, before merging the backend split, then formatted with Prettier.
It contains the full synthetic 20-client snapshot, including the evidence required to exercise the existing dashboard.
It is frozen historical output, not the replacement API contract and not a source of new analytics.
Do not manually repair or recalculate its financial values.

`../src/preview-contracts.ts` describes this fixture using handwritten types.
`../src/generated/openapi.ts` remains generated exclusively from the current live backend.
The Vite middleware serves the fixture at `/preview/dashboard` and echoes simulated review receipts at `/preview/reviews` without touching the SQLite ledger or persisting decisions.
Neither endpoint is mounted in normal Vite mode or FastAPI.
Preview builds go to `frontend/dist-preview`, separate from the normal `frontend/dist` served by FastAPI.
An optimized preview requires both `pnpm build:preview` and `pnpm preview`; a static FastAPI deployment does not provide the preview middleware.

This boundary follows [ADR 0002](../../docs/adr/0002-split-pipeline-along-data-team-seam.md), which removes the old projection API rather than retaining a second engine.
When Member 3 publishes the new Demo View Model, replace the temporary preview consumer types with its generated contract and update the live integration tests.
Do not restore `/api/monday-brief` or move formulas, ranking, narration, or evidence assembly into the frontend to bridge that gap.
