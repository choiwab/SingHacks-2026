# Phase A pipeline methodology review

Review date: 2026-09-05. Baseline As-of Date: 2026-08-26.

This is an independent automated implementation review against the corrected
`notebooks/eda.ipynb`, its written review in `notebooks/RM_REVIEW.md`, the versioned
`notebooks/reference_maps.json`, and the supplied Source Records. It is not a human
Relationship Manager Review Decision, bank policy approval, investment recommendation,
or tax opinion. Individual mappings still have human approval status `pending`.

## Conclusion

The reviewed publication preserves the principal financial distinctions required for
an internal demo: reported-mark performance and separate receipts, managed Portfolio
Mandate checks, canonical funding obligations, Daily cash versus deposits, economic
issuer screens, and source-backed financial limitations. The focused independent
checks pass. Client use remains conditional on the responsible Relationship Manager's
approval of mappings, policies, and generated content.

One material defect found during this review was corrected: an absent eligible
transaction ledger for one Client previously produced zero income and fees when
other Clients had records. The analytics now withhold those Facts, retain unavailable
income summary values, and carry a context limitation. The Data Quality Report also
records a source-backed Client-level missing-ledger warning. A missing ledger for the
whole dataset likewise does not establish zero receipts.

## Financial checks

| Area | Verified behavior |
| --- | --- |
| Funding deduplication | Fong's obligations are USD 16.7m, with cash cover 0.32297x and gross Daily-liquid cover 3.27096x. Nguyen's obligations are USD 8m, with 0.25888x and 1.56362x respectively. Linked commitments are counted once. |
| Deadlines | Fong, Nguyen and Margarethe escalate through confirmed near-term demand exceeding Daily cash. Their twelve-month AND escalation condition is false. Gross saleable securities do not cure a Daily-cash shortfall. |
| Margarethe scenario | Cash cover is 0.45917x and gross Daily cover is 5.27487x. The EUR 3.4m assumed equity-funded withdrawal leaves Equity at 65.72318%; a further EUR 6,041,645.883 reallocation is required to reach its 30% cap. These are arithmetic scenarios, not approved disposals or a verified tax liability. |
| Economic issuer screen | Lau's Golden Harbour exposure is approximately 29.5% and Pacific Rim Bank exposure approximately 17.6%. The unnamed bank basket remains explicitly unscreenable. Full-value issuer attribution does not establish delta, maximum loss, or forward accumulator notional. |
| Historical calculations | An As-of Date of 2026-03-15 uses the actual 2026-02-27 holdings observation. The later reference map is disabled and mapped event Signals are withheld. Dated note references must be available by the As-of Date. |
| Historical commitments | At 2026-06-30, Clients with commitments retain observed cash Facts but do not receive historical obligation, coverage or funding-gap outputs reconstructed from current called-to-date balances. The limitation is explicit. |
| Evidence and numeric integrity | All published Fact and Signal references resolve; Signal Fact references remain within their Client. Numeric values in published Facts, Signals and Evidence are finite. Every source-backed Phase A Data Quality Finding has resolvable Evidence. Generic policy limitations need not cite a source row. |

## Material source limitations carried forward

The baseline has 14 source-backed Phase A warnings. Under the repository contract,
`warning` means disclosure with publication permitted, while `error` blocks publication.
The warning label must not be interpreted as low financial materiality.

- Aranya's 2025-09-30 valuation represents 68.35% of its household's reported value.
  The warning explicitly identifies high materiality and rejects an unchanged mark
  as a current executable price or dependable exit-liquidity estimate.
- PF-0005 has unknown cost basis and unverified transferred/inherited tax-lot history.
  Disposal-tax advice requires original history from the transferring institution or
  estate executor. Supported Mandate and funding arithmetic remains available.
- Lau's facility movement leaves HKD 2m unexplained after documented drawdowns. The
  published finding cites CF-0002 and TXN-0013 and does not invent repayments or use
  of proceeds.
- Matched purchases and ending cost basis differ by USD 420,200 for CL-0007. Reported
  holdings are retained with a disclosed exception rather than repaired from trades.
- Transactions remain unreconciled to holdings. Receipts and financing costs are
  separate measures, not a validated total return. Non-Daily deposits, unknown
  sectors, and the incomplete ALTS target allocation also remain disclosed.

## Validation performed

Commands executed from the repository root:

```text
uv run pytest tests/test_phase_a_review.py
8 passed in 4.53s

uv run ruff check tests/test_phase_a_review.py app/analytics/phase_a_quality.py
All checks passed!
```

The eight checks include whole-ledger and individual-Client ledger removal,
historical snapshots and commitments, mandatory financial warnings, baseline funding
and issuer comparisons, and publication-wide numeric/Evidence integrity. These are
behavioral tests against the corrected methodology and reviewed baseline figures,
not a substitute for validating the economic truth or completeness of the synthetic
Source Records. The broader analytics, pipeline and agent suites are reported by
their respective implementation checks, not claimed as executed in this review.

## Remaining approval and scope limits

Human approval is still required for the manually curated issuer/event mappings and
demo thresholds. Funding resources remain gross of encumbrance, execution costs,
settlement delays, FX and tax confirmation. Static reference records do not establish
historical commitment balances. Five observations and stale marks cannot establish
continuous drawdown or reconciled total return. Accumulator remaining notional and a
calibrated Strait-reopening stress are unavailable, so no quantified loss scenario
is asserted. No external source or jurisdiction-specific legal conclusion was needed
or independently verified for these implementation checks.
