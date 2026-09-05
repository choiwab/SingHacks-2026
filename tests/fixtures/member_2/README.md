# Provisional Member 2 integration fixtures

All communication records are authored synthetic demo extensions. They were not fetched from Gmail,
Teams, notes or calendar accounts. Their `based_on` references identify supporting original RM notes
where applicable; the invented messages are not verbatim copies of those notes. Their source type
describes the integration being simulated, not a successful external connection.

The curated facts and their evidence were exported from the existing deterministic
`build_monday_brief(data, as_of=2026-08-26)` projection for Margarethe. **Signal scores are provisional:**
each fixture signal carries the existing client-level priority score and components, because the
repository has no approved per-signal score contract yet. Member 4 must replace these signal fixtures
with its finalized outputs. Member 2 does not calculate or adjust those scores.

The updated bundle changes only the deadline signal's topic and uncertainty. It does not invent a
cash shortfall or alter any financial amount. The updated communication manifest adds an email about
tax-payment planning, low volatility and willingness to discuss reducing risk. The older preference
to defer portfolio changes remains available, so the brief flags it for confirmation.

`golden.*.json` freezes the expected generated meeting packs for initial, combined, financial-only,
and communication-only runs. The demo verifier only accepts those frozen claims (plus the one example
RM opening used by the tests). It is a deliberately limited test double and is never a production
Evidence Gate. The graph requires an explicitly supplied verifier at construction.

Input records use stable dates and IDs. Retrieval timestamps do not affect content fingerprints.
Each content hash covers source text and provenance; changes invalidate old chunk citations.

The integration migration represents each authored legacy fixture fact using a canonical
one-number Fact and retains the full original calculator inputs plus authored wording in
`fact_descriptions`. `fixture.legacy.*` formula IDs explicitly identify these demonstration
conversions. Golden input fingerprints changed with this schema migration; generated claims
and financial wording remain the same. These provisional fixtures are never injected into
the 20-client pipeline's published financial artifacts.
