# Split the deterministic engine along the data-team seam

The original `app/pipeline.py` computed facts, extracted beliefs from RM notes, ranked clients, and wrote prose in one module. The PRD gives formulas and signal logic to Member 4 (analysis), plumbing to Member 3 (pipeline), and all prose and insight selection to Member 2 (agents), and forbids the data layer from generating prose. We split the module rather than rewrite or wrap it: ingest, validation, evidence identifiers, publishing, and hashing live in `app/pipeline/`; the fact formulas and priority scorer moved verbatim to `app/analytics/` so Member 4 starts from tested code; the belief extractor, gap matcher, narrator, and scenario engine were deleted because their job now belongs to the agent layer. Any number the product shows is computed in `app/analytics/` and published by `app/pipeline/`, never elsewhere.

## Considered options

- Greenfield `app/pipeline/` next to the untouched monolith: two engines for two days and re-implementation of working validators.
- Wrap the monolith and reshape its output: every schema stays constrained by the old projection shape and formula ownership never becomes clean.

## Consequences

- `app/analytics/` contains code that visibly predates the package; that is intentional, not a misplaced file.
- `GET /api/monday-brief`, its projection models, and the Monday Brief frontend consumers were removed with the prose code rather than kept as a parallel path.
