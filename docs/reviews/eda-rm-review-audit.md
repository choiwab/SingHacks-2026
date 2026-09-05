# EDA audit against RM_REVIEW.md

## Implementation follow-up: 2026-09-05

All 35 numbered requests are now addressed in `notebooks/eda.ipynb`: the two already-satisfied
requirements are retained and the other 33 are implemented. The final notebook includes a
35-row traceability table, policy-boundary assertions, numerical reconciliation, and resolution
checks for every analytical Signal's source Evidence. All 48 code cells execute successfully.
`ruff check` and `ruff format --check` pass for the notebook. Performance and funding plots
were visually inspected; outputs were regenerated from the revised code.

The versioned `notebooks/reference_maps.json` records issuer, structured-product, event-channel,
wealth-overlap, and currency-objective mappings. Their external human RM approval remains pending;
the notebook does not claim that an AI review is a bank committee approval. Production analytics
provider integration and scenario calibration are the next implementation steps.

Independent source reconciliation corrected several numbers in the review itself:

| Item | Review figure | Verified figure used in notebook |
| --- | --- | --- |
| New positions' post-purchase move at current FX | About -USD 0.65m | -USD 680,254.04 |
| Al-Mansoori's starting Strait sleeve gain | About USD 2.3m | USD 1,894,044.53, plus 2.2702pp from the rest of the opening portfolio |
| Margarethe's additional equity reallocation after paying EUR 3.4m externally | About EUR 8.4m | EUR 6,041,645.88; the larger figure is approximately the excess before withdrawal |
| Accumulator reference stock below HKD 17.20 strike | 24% | 18.0233%; 24.1935% is its decline from the starting stock price |

The notebook also distinguishes gross household income from fixed-income sleeve losses,
documents the HKD 2m unreconciled portion of Lau's facility balance increase, and keeps Ravi's
sale-conditional tax need separate from unconditional funding obligations. Holdings, original RM
notes, and the original review are unchanged.

To reproduce the notebook's execution and refresh its saved outputs from the repository root:

```bash
uv run --group analysis python - <<'PY'
from pathlib import Path
import nbformat
from nbclient import NotebookClient

path = Path("notebooks/eda.ipynb")
notebook = nbformat.read(path, as_version=4)
NotebookClient(
    notebook,
    timeout=180,
    kernel_name="python3",
    resources={"metadata": {"path": str(path.parent.resolve())}},
).execute()
nbformat.validate(notebook)
nbformat.write(notebook, path)
PY
uv run ruff check notebooks/eda.ipynb
uv run ruff format --check notebooks/eda.ipynb
```

## Historical pre-fix audit

The findings below describe the original notebook at `7a33ebb`, before the implementation
follow-up above. They are retained as the problem statement, not the current completion status.

Date: 2026-09-05.

Scope: compare all 35 numbered required changes in `notebooks/RM_REVIEW.md` with
the code, saved text outputs, narrative, and frozen specification in `notebooks/eda.ipynb`.
This is an implementation-status audit, not an independent validation of the review's
financial calculations or legal assertions. The notebook was not re-executed or modified.

## Verdict

The notebook has not been revised after the RM review was added. Two requests are already
satisfied in the pre-review notebook: **6 (managed-portfolio mandate scope)** and
**9 (binding sustainability exclusions)**. The other **33 requests remain incomplete**.
Several have partial groundwork, which is distinguished from satisfying the requested change below.

An item is complete only when the requested behavior or disclosure is present in the relevant
analysis and specification. A raw source row appearing in an output, a future pipeline action,
or an unrelated calculation does not establish that a requested signal or correction is implemented.

### Revision evidence

- Local HEAD: `7a33ebb28d552f1357bac78f8f016ac74952712a`.
- Fetched GitHub `origin/feat/data`: `911f912433a41d1789374d1df42dd1c8b40798e6`.
- Last notebook modification: `2b2e255`, before the review was added.
- `7a33ebb` adds the review and changes two pipeline Python files, but not the notebook.
- `911f912` merges main, but does not change the notebook.
- `git diff 2b2e255 origin/feat/data -- notebooks/eda.ipynb` is empty.
- Notebook blob at both local HEAD and fetched branch tip: `ad61d00793c08133db1335fcc59354160f7d7757`.
- All 47 code cells have execution counts; no saved error outputs are present. This establishes
  saved execution state, not analytical correctness or successful execution in today's environment.

## Item-by-item audit

Cell numbers below are **one-based positions in the notebook**, including Markdown cells.
They are not execution counts. For example, cell 58 means `.cells[57]` in the notebook JSON.

### Preprocessing: requests 1-5

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 1 | Incomplete | Cell 57 classifies transaction types as income/cost/flow/activity and prints counts. It does not compute per-client income received or fees paid. Sections 11 and 12.2 still describe transactions as an event/intent source only. Add the monetary Facts, the non-reconciliation disclosure, and income beside price performance. |
| 2 | Incomplete | Cell 18 computes `new_position_effect` using quantity change times ending price and ending FX. It does not use matching transaction subscription cost. The printed +0.76% and section 13 lack the requested caveat that new positions' own post-purchase moves are excluded. |
| 3 | Incomplete | Cell 56 explicitly sets `DQ-05` severity to `medium`; saved outputs agree. The stale Aranya mark has not been upgraded to high. |
| 4 | Incomplete | Sections 11 and 12 already identify the transfer date, missing basis, and tax-output restrictions. They do not explain that the other eight positions' bases are transfer-date bases, distinguish since-transfer P&L from since-purchase P&L, or request tax-lot history from the transferring institution/estate executor. |
| 5 | Incomplete | Cell 34 maps “Global Energy Majors ADR” to `SYN-EQ-0008`. The mapping comment does not disclose that a diversified fund is being used as an approximation for the named basket leg. |

### Mandate: requests 6-10

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 6 | Already satisfied | Cell 28 groups by portfolio and asset class using `market_value_base`, joins each portfolio's mandate, and excludes Custody. Section 12.3 rule 7 explicitly says to test mandate bands per managed portfolio. Household concentration is separately labelled a risk screen in cell 36. This was present before the review. |
| 7 | Incomplete | Cell 28 begins with asset classes present in holdings and left-joins mandate rows. It does not construct managed portfolios × all six mandate classes with zero fill. A missing held class can therefore disappear from the minimum-band test. |
| 8 | Incomplete | Cell 36 tests household position percentages against the household's tightest limit and explicitly disclaims this as a compliance finding. There is no separate managed-portfolio `weight_pct` test or the requested greater-than-2pp escalation policy. |
| 9 | Already satisfied | Cell 31 identifies `SUSBAL` holdings with `sustainability_excluded == 'Y'` without a weight cutoff. Section 5 calls exclusions binary and always high; section 12.5 also includes the exclusion test and high severity. The review overstates this omission for the notebook being audited. |
| 10 | Incomplete | Section 5 describes N-010, N-013, and N-005; section 12 has waiver/restriction rules. But breaches are not emitted with the requested three-way classification and note ID. Cell 59 instead uses `drift_origin: inherited_transfer_in`, without the requested standardized classification or re-solicitation actions. |

### Funding: requests 11-15

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 11 | Incomplete | Cell 39 directly sets `obligations_usd = needs_12m_usd + uncalled_usd`. There is no CN-016/COM-001/COM-002 or CN-008/COM-003 deduplication. The catalogue still ends at DQ-10, and section 7 retains the old coverage figures. |
| 12 | Incomplete | Cell 59 still prints `cash_cover_x < 1.0 warn; daily_cover_x < 1.5 escalate`. Neither it nor section 12.5 adds the required cash-cover AND daily-cover escalation condition. |
| 13 | Incomplete | Cell 39 sums needs without a certainty filter. Sections 7 and 12.2 still propose Likely 0.7 and Conditional/Aspirational 0.3, contrary to the requested full Confirmed/Likely inclusion, explicit contingent treatment, and Aspirational exclusion. |
| 14 | Incomplete | No rule tests a Confirmed need within six months against Daily-cash cover. Cell 59 hardcodes Margarethe's funding severity to high, but this does not implement the requested rule and does not follow its own printed daily-liquid threshold. |
| 15 | Incomplete | Cells 39 and 41 define cash solely by the `Cash and Equivalents` asset class. They do not separate Daily cash from Monthly fixed deposits. Section 7 describes cash as available today, without the requested deposit distinction or wording. |

### Collateral: requests 16-17

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 16 | Incomplete | Section 8 still says CF-0002 is “rising every single snapshot” and “has risen at every observation,” despite printing the initial 53.93 to 53.53 decline. Section 13 repeats the incorrect trend. |
| 17 | Incomplete | Cell 44 computes `ever_breached`, and sections 8/13 discuss a market-driven cure. There is no combined fragile-cure flag checking previous breach, no drawn reduction, and unresolved-event collateral concentration. Section 12.5 retains only proximity/trend criteria. |

### Look-through: requests 18-22

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 18 | Incomplete | Section 6 displays the zero-direct-holding cases. Section 12.5 still requires exposure above the household's tightest limit, with no informational trigger for at least 10% exposure and zero direct holding. Displaying the examples does not make them fire under the frozen rule. |
| 19 | Incomplete | Cell 34 actually attributes current market value, but section 6 and section 12 repeatedly call it full notional and use `worst_of_full_notional`. The requested terminology and explicit prohibition on summing cross-issuer rows are not supplied. |
| 20 | Incomplete | Section 6 still describes all six structured products as worst-of notes and the approach as deliberately conservative. The accumulator is not flagged as understating forward exposure; there is no remaining-accumulation-notional request. |
| 21 | Incomplete | Cell 34 loops over a short curated `ISSUER` dictionary. There is no default issuer identity for every qualifying instrument. Pacific Rim Bank's perpetual is absent from that issuer map, so the requested exposure is missing from this analysis. |
| 22 | Incomplete | Cell 34 assigns `SYN-SP-0506` an empty list and comments that the three banks are not in the instrument universe. This recognizes missing mapping, but produces no explicit unnamed/unscreenable exposure disclosure or alert. |

### Belief gaps: requests 23-27

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 23 | Incomplete | Section 10 separately discusses a waiver, dealing restrictions, and an unanswered question. Nevertheless section 12.5 still says all nine claims are contradicted, and the comparison table does not classify six contradictions versus constraints/corroborations/question. |
| 24 | Incomplete | Section 10 and cell 54 still compare N-001 directly with the household's 41.4% coal stake. They do not distinguish the acknowledged custody holding from the April client-requested managed-portfolio FCN, or use N-002 and the requested 6.2% managed exposure. |
| 25 | Incomplete | Cell 54 presents Cheung's and Chalermchai's fixed-income mark declines as “cost” figures. Neither comparison includes income received. |
| 26 | Incomplete | N-024 appears in the generic source-note listing, but Elena is absent from `said_vs_data`. The requested 5% intended hedge versus 14.04% current gold comparison and overlapping luxury exposure are not added. Optional consideration of Lindqvist is also not developed into that table. |
| 27 | Incomplete | Note IDs and manual RM review are already present. The comparison table still uses `you_said` without a uniform dated “as recorded in RM note” label or an explicit RM-paraphrase disclosure before client use. |

### Event, currency, suitability: requests 28-31

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 28 | Incomplete | Sections 9 and 12 specify a curated/version-controlled transmission map and event citations. Executable analysis in cell 50 uses only `STRAIT_INSTRUMENTS` and a transmission keyword filter. There is no complete mapping of every channel or mapping-version field on alerts. |
| 29 | Incomplete | Narrative discusses reopening risk for Hartono and Al-Mansoori, but there is no alert direction field or complete directional treatment across channels. Cell 50 counts the full Broad Commodity Index value without the requested approximation disclosure. |
| 30 | Incomplete | Section 12.5 has the >40% threshold and mentions base-currency obligations, but does not require a Confirmed need within 24 months or an income/decumulation objective. Cell 48 computes only currency shares. The “assumed unhedged” disclosure is missing. |
| 31 | Incomplete | Section 12.5 already uses score ≤3 and base-currency loss worse than -5%. It does not add the alternative maximum-drawdown threshold below -7% or show income. The request to drop “realised volatility” is already moot: that wording is absent from the current definition. |

### Demo narrative: requests 32-35

| Review # | Status | Notebook evidence and remaining change |
| --- | --- | --- |
| 32 | Incomplete | Cell 25 computes endpoint household value ratios without removing new-position additions. Section 4 still quotes Al-Mansoori +25.9%, Kim +25.3%, Hartono +23.4%, and Zhang +18.6%; section 13 repeats the inflated Al-Mansoori return. No per-client same-store replacement is present. |
| 33 | Incomplete | Sections 9 and 13 still attribute all Al-Mansoori's gains to the conflict. There is no computed split between starting Strait holdings and the rest of the portfolio. |
| 34 | Incomplete | Sections 7 and 13 still frame selling equity for the tax bill as the shared solution. No post-sale allocation/glide-path calculation, remaining cure amount, renewed N-005 instruction check, or tax-lot remediation action is attached. |
| 35 | Incomplete | Cell 46 displays raw facility drawdown transactions, but Lau's demo story does not explain the HKD 4m accumulator-settlement financing or add his 17.6% Pacific Rim perpetual exposure. Raw transaction visibility is not the requested narrative integration. |

## Important distinctions

1. **No post-review revision is not the same as zero existing coverage.** Requests 6 and 9
   are already satisfied, and several others build on work already in the notebook.
2. **The review has some stale wording.** Its claims about missing exclusions and the
   “realised volatility” definition do not fully match this notebook. Its numbered
   preprocessing “Decisions” also need mapping to the current section 12 blueprint.
3. **Correcting Markdown alone would be insufficient.** Returns and funding figures come from
   executable calculations and saved outputs. The narrative, code, charts/tables, feature
   catalogue, signal rules, and worked JSON example must agree after revision.
4. **The worked funding example is internally inconsistent.** Cell 59 assigns high severity
   to Margarethe while displaying daily-liquid cover above its printed escalation threshold.
   Adding the requested near-term Daily-cash rule would provide a reasoned basis for escalation.

## Additional suggestions outside the numbered 35

The review's section 4 proposes four further additions. They are separate from the count above:

- **Stale-mark concentration signal:** age/concentration are discussed, but the proposed
  greater-than-two-quarters AND greater-than-25% trigger is absent.
- **Tax-aware household Facts:** tax domicile and basis caveats exist, but the requested
  household gain/loss presentation is not implemented.
- **Unactioned promises/questions:** N-028 is explicitly discussed as urgent, but there is no
  generalized outstanding-follow-up artifact or signal covering the proposed notes.
- **KYC/review dates:** near-term KYC context and a planned date-derived field exist, but this
  is not included as a frozen priority signal.

## Recommended revision order

1. Correct performance decomposition and per-client returns; compute income/fees.
2. Deduplicate liabilities and settle certainty, cash tiers, and funding escalation rules.
3. Complete mandate, issuer, collateral, event, currency, and suitability definitions.
4. Rewrite belief comparisons and the three demo stories using corrected calculations.
5. Reconcile section 12 and the worked JSON with those decisions; rerun all notebook cells
   and inspect regenerated outputs before treating the notebook as the implementation specification.

No production-code implementation or numerical revalidation is claimed by this audit.
