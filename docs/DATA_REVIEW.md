# CSV data review

Reviewed all 11 CSV files in `data/`: 1,723 rows, 20 clients, 24 portfolios, and five snapshots containing 1,015 holding records.
The current snapshot is **26 August 2026**, with total reported client AUM of **USD 596,220,638.06**.
This review uses that scenario date, the data dictionary, and the supplied event log; it does not validate synthetic market history against external sources.
The 28 RM notes were also read to distinguish intended client circumstances from data errors.
Source CSVs were not changed.

**Main conclusion:** individual snapshots reconcile well, but transaction-to-snapshot accounting does not.
The data supports useful allocation, concentration, liquidity, and collateral analysis, provided missing inputs and history limitations remain visible.
It does not support treating raw AUM changes as reconciled investment returns.

**High-priority data quality findings**

| Finding | Evidence | Consequence |
|---|---|---|
| Cash does not roll forward with recorded transactions | All 29 cash/cash-equivalent position quantities are constant across all five snapshots; deposit balances do not reflect recorded cash movements; In PF-0009, TXN-0001 spends USD 956,800 on gold on 22 January, while USD call cash remains USD 1.6m before and after; this is the only transaction recorded for that portfolio through 27 February; | The files are not a complete self-reconciling ledger; an offsetting funding movement is absent, or cash snapshots are stale; Raw AUM growth includes purchased assets without a corresponding cash reduction in this example; |
| Gold cost basis ignores the new purchase price | PF-0009 / SYN-CM-0402 grows from 6,000 to 8,000 units; Opening cost is USD 1,609,800; TXN-0001 adds USD 956,800; Expected cost is USD 2,566,600, but all four later snapshots report USD 2,146,400; | Cost is understated, and unrealised gain overstated, by **USD 420,200** based on the supplied transaction history; the implied average cost should be USD 320.825, rather than the unchanged USD 268.30; |
| Facility history has an unexplained HKD 2m increase | CF-0002 drawn rises from HKD 52m on 27 February to HKD 58m on 31 March; TXN-0013 records only HKD 4m of additional borrowing, consistent with RM note N-018; | The loan balance needs another HKD 2m activity record or a correction; the reported LTV arithmetic itself is correct; |
| Alternatives mandate targets total 93% | ALTS targets in `mandates.csv` are 3% cash, 5% fixed income, 0% equity, 85% alternatives, 0% commodities, and 0% structured products; | The target allocation leaves 7 percentage points unspecified; Allocation bands can still be checked, but a target-based rebalance is underdefined; |
| Holdings precede acquisition and portfolio inception | PF-0005 has nine holdings dated 31 December 2025, while the portfolio inception, all nine acquisition dates, and the transfer-in are 16 February 2026; | This may be backfilled predecessor history, but it is not labeled as such; Do not treat it as an ordinary continuously held portfolio or count the transfer on top of an already populated opening balance; |

Exact examples: [gold purchase](../data/transactions.csv#L4), [opening gold position](../data/holdings.csv#L287), [post-purchase gold position](../data/holdings.csv#L299), [opening cash](../data/holdings.csv#L297), [post-purchase cash](../data/holdings.csv#L309), [facility history](../data/credit_facilities.csv#L3), [drawdown](../data/transactions.csv#L7), [ALTS targets](../data/mandates.csv#L38), and [pre-inception holdings](../data/holdings.csv#L96).

Capital calls show a similar accounting limitation.
PF-0020 records USD 3.2m paid to Meridian Private Equity in February and USD 1.8m paid to Global Infrastructure Debt in July, yet both position quantities and costs remain constant, as does the sleeve's USD 900,000 cash balance.
The infrastructure fund's current `called_to_date` is USD 6.2m, versus a holding cost basis of USD 2.5m.
These are reconciliation exceptions requiring transaction, distribution, and funding history; they are not enough evidence to invent replacement balances.

**Other data quality findings and modeling traps**

| Finding | Evidence and interpretation |
|---|---|
| Unknown cost basis | PF-0005 / Nordvind Industrial AB lacks `avg_cost_local`, `cost_basis_base`, and both unrealised P&L fields in all five snapshots; the current position is **EUR 3,732,300**, or **18.37%** of the portfolio; TXN-0018 explicitly says some transferred tax-lot history was unavailable; Aggregate unrealised P&L is therefore incomplete, and missing values must not become zero; |
| Missing sector | SYN-SP-0506 has no sector in the instrument master or any of its five holding records; its underlying description is an Asian banking basket; the current position is **EUR 1,094,505.49**, or **5.39%** of PF-0005; sector grouping can silently drop it unless an explicit unknown category is retained; |
| Wealth-band labels disagree with the dictionary | CL-0012 is labeled UHNW at USD 28.03m, and CL-0014 at USD 26.49m; the dictionary defines UHNW as USD 30m and above; these could be retained historical classifications, but that policy is not documented; |
| Duplicate representations of future obligations | CL-0006's USD 3m private-equity need appears in both CN-008 and COM-003; CL-0017's USD 15.8m need in CN-016 equals COM-001 plus COM-002; Summing both files would double-count **USD 18.8m**; the files need an obligation-linking rule; |
| Ambiguous tuition schedule | CN-007 says USD 5m for two children's US university fees, September 2026 through September 2030, with recurrence `Annual instalments`; it does not specify whether USD 5m is the total program budget or the amount of each annual instalment; the size warrants confirmation, but is not proof of a typo; |
| Stale valuation with material client exposure | Ravi's Aranya Technologies holding is **USD 31.92m**, or **68.35%** of his total AUM, with valuation date 30 September 2025, **330 days** before the current snapshot; A June review explicitly retains the price; this is a disclosed stale mark, not evidence of a calculation error; |
| Private-market mark provenance is incomplete | Only Aranya has a valuation date older than the snapshot; other private-market holdings use the snapshot date, despite documentation saying underlying marks can lag a quarter; the schema cannot reliably distinguish a report date from the underlying valuation date for those funds; |
| Gold narrative chronology conflicts | TXN-0001 is dated 22 January and says the purchase followed gold moving through USD 5,000; the authoritative event log dates the first move above USD 5,000 to 26 January; the narrative or event/trade date needs clarification; |
| KYC documentation overstates what is in the data | The dictionary says some reviews are overdue, but none are overdue at the scenario date of 26 August; the earliest deadline is Tan's 31 August 2026; As-of date handling matters here; |

Missing client age is expected for CL-0017, a family-office entity.
Missing quantities and prices on fees, income, withdrawals, and administrative transactions are generally expected for those transaction types.
Blank underlying references on ordinary instruments are also expected.

**Interesting client and portfolio findings**

The current snapshot has **14 asset-allocation band breaches across nine non-custody portfolios**, plus **13 flagged single-position limit breaches across nine non-custody portfolios**.
These counts overlap and are not counts of distinct clients or unique issues.
Custody portfolios were excluded from mandate testing, as the dictionary requires.
Single-position checks use `concentration_limit_applies=Y`, so diversified funds and deposits are not incorrectly tested against single-name limits.
The counts are raw numerical conditions before considering documented waivers or remediation discussions.

| Client | Finding | Why it is interesting |
|---|---|---|
| Margarethe, CL-0003 | Conservative portfolio has **71.46% equity** against a 30% maximum; fixed income is **9.15%** against a 45% minimum; | Her notes explicitly request a safer portfolio; the EUR 3.4m inheritance-tax need exceeds EUR and CHF cash combined, converted to EUR, by approximately **EUR 1.84m**; other daily-liquidity assets exist, so this is a cash-funding decision rather than evidence of insolvency; |
| Aishah, CL-0005 | **21.30%** of her sustainable portfolio is in explicitly excluded instruments: Global Energy Majors and Sunrise Palm; equity totals **67.74%**, above the 55% limit; | Her note says she believes the portfolio is aligned with the sustainability policy; this is a direct mismatch between her understanding and the instrument exclusion flags; |
| Ravi, CL-0002 | CF-0001 crossed its **75%** LTV trigger in June at **75.64%**; current LTV is **73.71%**; | The June-to-August cure came from higher lending value, with borrowing unchanged at USD 6.5m; current trigger buffer is only **USD 114,107.50**, despite reported `headroom` of USD 2.32m; his separate stale unlisted holding dominates household AUM; |
| Lau, CL-0014 | CF-0002 is at **69.41%** LTV versus a **70%** trigger; | Trigger buffer is just **HKD 496,151**, while reported `headroom` is HKD 25.57m; A **0.85% decline in lending value**, with borrowing unchanged, reaches the trigger; Shares, a perpetual, an accumulator, and property link his portfolio to the same property theme as his business; |
| Hartono, CL-0001 | A single coal/energy stock is **41.42% of total client AUM**, held in custody; | His main managed portfolio can look diversified in isolation; his stated objective is diversification away from the family coal business, yet he also owns a shipping/energy note; CF-0005 breached its 70% trigger in December and February, then fell to 58.86% in March while borrowing remained SGD 8m; the improvement was collateral-driven; |
| Fong family office, CL-0017 | The alternatives sleeve has **USD 900,000** of daily-liquidity assets versus **USD 15.8m** of outstanding commitments spread across future windows; two funds exceed its 25% position cap; | At household level, daily-liquidity assets total **USD 54.62m**, including **USD 5.39m** of cash/cash equivalents; this is a sleeve-funding and timing problem; treating the family as unable to meet every commitment would ignore its other portfolios; |
| Zhang, CL-0013 | Direct Helios shares plus the Helios-linked note account for **22.49%** of portfolio market value; | Direct shares alone are 15.40%; Looking only at equity positions obscures the additional linked product; the combined number is a market-value footprint, not a delta-adjusted exposure estimate; |
| Tan, CL-0011 | A Conservative portfolio has **47.28% alternatives**, against a 15% maximum; fixed income is 24.47%, below its 45% minimum; | The notes describe delayed succession planning, while a requested private-credit redemption is gated; Cash held in a monthly-liquidity deposit should not be classified as immediately available; |
| Andreas, CL-0009 | Cash/cash equivalents are **44.98%**, against an 18% maximum; | His notes describe repeated postponement of an agreed deployment plan; the remaining Nordvind position is also above its single-position limit; Quantifying foregone benchmark return would require a benchmark time series that is not supplied; |
| Alistair and Elena | Commodities are **18.93%** and **14.04%**, respectively, versus 10% ceilings; | Alistair's note explicitly records a suitability waiver and client-directed gold purchase; the numerical breach should remain visible with that context; Elena's note describes an originally smaller hedge that has grown; |
| Abdullah, CL-0019 | Shipping and energy funds/shares plus the shipping-energy note comprise **42.13%** of portfolio market value; | His objective is diversification away from his Gulf logistics business, but these assets share a related economic theme; the basket note cannot be allocated precisely among underlying names from the available fields; |

The trigger-buffer formula is `margin_call_ltv_pct / 100 * lending_value - drawn`.
The CSV's `headroom` is instead `lending_value - drawn`.
Both can be arithmetically correct, but presenting the latter as safe additional borrowing would be misleading.
The lending-value decline calculation assumes unchanged borrowing and measures a change in haircut-adjusted collateral value, not necessarily the same percentage change in raw portfolio market value.

These liquidity comparisons use current snapshot values and stated dealing-frequency labels.
They do not guarantee sale proceeds, settlement timing, collateral release, or future funding availability.
Future needs retain their certainty and recurrence distinctions; the entire amount in a multiyear window is not assumed payable immediately.

**Checks that passed**

- All 11 CSVs parse cleanly with consistent field counts, no malformed records, no duplicate logical keys, and no leading or trailing whitespace in populated string fields.
- Client, portfolio, instrument, mandate, and collateral references resolve; portfolio ownership agrees across files.
- All 1,015 holdings match instrument-master prices at their snapshot dates, and populated instrument metadata agrees across the two files.
- Quantity times local price, snapshot FX conversion, portfolio weights, haircut-adjusted lending values, and available P&L arithmetic reconcile within stored rounding precision.
- All 120 portfolio/date AUM totals reconcile to holdings, and current client AUM totals reconcile to portfolios.
- All 25 facility/date collateral aggregates, LTV calculations, and headroom calculations reconcile within rounding precision.
- Commitment arithmetic reconciles: committed equals called-to-date plus uncalled.
- Recorded trade quantities and prices reconcile to trade cash amounts where both fields are present.
- Date fields parse, settlement never precedes trade, valuation dates never follow their snapshot, and cash-need windows are ordered correctly.
- No negative holding quantities, prices, market values, or lending values were found.

Passing these checks means internal arithmetic is consistent; it does not resolve the transaction-history exceptions above.
For example, the gold row's P&L equals market value minus its recorded cost, even though that recorded cost does not reconcile to the purchase.

**Suggested order of follow-up**

1. Resolve cash roll-forward, gold cost basis, the HKD 2m loan discrepancy, and the missing 7% ALTS target allocation before publishing reconciled performance or target-based rebalancing.
2. Label predecessor history, missing cost basis, unknown sector, and stale valuation provenance explicitly.
3. Link duplicate cash needs and commitments, and clarify tuition recurrence before projecting cash requirements.
4. Surface mandate conditions with custody exclusions and waiver context, and distinguish margin-trigger buffer from reported lending headroom.
5. Present the client-level concentration and funding findings with source rows, dates, and the stated limitations above.
