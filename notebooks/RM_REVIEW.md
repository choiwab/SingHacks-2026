# Senior RM Review — Phase A EDA (`notebooks/eda.ipynb`)

**Reviewer:** Senior private banker, 25 years Singapore/Hong Kong booking centres; former market head; suitability and credit committee member.
**Date:** 2026-09-05 (dataset "today" = 2026-08-26).
**Scope:** The Phase A notebook, its section 12 frozen 8-signal shortlist and preprocessing decisions, the data-quality catalogue, and the demo narrative. Every load-bearing number was re-derived independently from the raw `data/` files with pandas; nothing was taken on the notebook's word.

---

## 1. Per-module verdicts

| # | Module | Verdict | Headline |
|---|--------|---------|----------|
| 1 | Preprocessing + DQ catalogue | **APPROVED WITH CHANGES** | Rules are committee-grade; income received from transactions is a commercially dangerous blind spot |
| 2 | Mandate band breach | **APPROVED WITH CHANGES** | 14/9 count verified exactly; single-position and exclusion-list compliance tests are missing from the frozen signal |
| 3 | Funding gap | **APPROVED WITH CHANGES** | Genuine double-count: commitments restated in planned_cash_needs (USD 15.8m + USD 3.0m) counted twice |
| 4 | Collateral stress | **APPROVED WITH CHANGES** | Best-verified section of the notebook; one false trend sentence; cured breach CF-0005 produces no alert under the frozen spec |
| 5 | Look-through concentration | **APPROVED WITH CHANGES** | All numbers verified; threshold cannot fire on its own headline finding; accumulator treatment is anti-conservative, not conservative |
| 6 | Belief-versus-data gap | **APPROVED WITH CHANGES** | Six pairs are genuinely strong; "all nine contradicted" is an overclaim; Hartono and Cheung pairs would not survive the client's comeback |
| 7 | Event / currency / suitability drift | **APPROVED WITH CHANGES** | Suitability drift fires on exactly the right two clients; currency threshold fires on 7/20 (noise); event channel map must be generalized |
| 8 | Demo narrative | **APPROVED WITH CHANGES** | **Most important finding of the review:** per-client returns violate the notebook's own preprocessing decision 3 — Al-Mansoori is +9.7% ex-new-positions, not +25.9% |

No module was rejected. Every headline story survives correction; several quoted numbers do not.

---

## 2. Required changes (numbered, exact)

### Preprocessing (Module 1)

1. **Amend Decision 1 (holdings-as-truth).** Add: "The pipeline MUST compute income received per client (Dividend + Coupon + Interest + Distribution) and fees paid from `transactions.csv`, labelled 'not reconciled to positions'. Any performance statement shown for an income-oriented client must display income received alongside the price return." Verified magnitudes: CL-0012 received ≈ USD 1.15m (0.86m coupons); CL-0004 ≈ USD 1.55m; book management fees ≈ USD 1.8m.
2. **Amend Decision 3 (decomposition).** New-position effect must be measured at subscription cost from the matching transaction rows (TXN-0001…0007, ≈ USD 15.3m at current FX); the post-purchase move on those positions (≈ −USD 0.65m; end value 14.66m) is performance. At minimum, the +0.76% ex-new figure must carry the caveat "excludes the new positions' own moves since purchase."
3. **Upgrade DQ-05 (stale Aranya mark) from medium to HIGH.** An 11-month-stale mark pricing 68.4% of CL-0002's household is not the "one quarter behind" norm the data dictionary declares; severity must reflect client-level impact.
4. **Strengthen the PF-0005 spec (DQ-03/04).** (a) State that the cost bases on the other eight PF-0005 positions are struck at the 2026-02-16 transfer — unrealised P&L there means "since transfer", never "since purchase", and no tax conclusion may be drawn (under German succession the heir carries the decedent's basis, which we do not hold). (b) Emit the action item: request tax-lot history from the transferring institution / estate executor before the Oct–Dec tax conversation.
5. **Look-through caveat:** basket leg "Global Energy Majors ADR" is mapped to SYN-EQ-0008, a diversified FUND — disclose the approximation.

### Mandate signal (Module 2)

6. **Reword the definition:** band tests run per MANAGED portfolio against that portfolio's own mandate on `market_value_base`; household allocation is context only and is never tested against a band.
7. **Fix the latent method bug:** build the test grid as managed portfolios × all six mandate asset-class rows with zero fill, so a mandated class held at 0% can fire its min-band breach. (Today the two methods agree — verified 14 = 14 — but the pipeline must not inherit the fragile groupby.)
8. **Add the single-position compliance test:** per managed portfolio, `weight_pct > max_single_position_pct` where `concentration_limit_applies = 'Y'`. Fires 13 times today (Yamamoto employer stock 20.10% vs 12; Margarethe Nordvind 18.37% vs 10; Fong 35.30% vs 25; Lau three positions; etc.). De-minimis: flag all, escalate only >2pp over.
9. **Add the exclusion-list test:** any `sustainability_excluded='Y'` instrument inside a mandate with binding exclusions fires at ANY weight and escalates (Aishah: 21.30% = Global Energy Majors 11.13 + Sunrise Palm 10.17). This is a documentation failure, not drift.
10. **Add breach classification** {drift | client-directed | waiver-on-file} + note id on every breach (N-010 waiver → monitor + confirm waiver current; N-005/N-013 client-directed → alert stands, action becomes documented advice / re-solicitation).

### Funding gap (Module 3)

11. **Deduplicate needs against commitments.** CN-016 (USD 15.8m, CL-0017) = COM-001 (14.0m) + COM-002 (1.8m) restated; CN-008 (USD 3.0m, CL-0006) = COM-003 (3.0m, same fund, same window). Corrected covers: CL-0017 cash 0.32x (not 0.17x), daily 3.27x (not 1.68x); CL-0006 cash 0.26x (not 0.19x), daily 1.56x (not 1.14x — crosses the escalation line). Record as DQ-11.
12. **Fix the escalation boolean:** warn when cash cover < 1.0x; escalate when cash cover < 1.0x AND daily cover < 1.5x. (As frozen, daily < 1.5x alone can escalate a client sitting on 1.2x pure cash.)
13. **Carry certainty:** Confirmed/Likely count in full; "Conditional on the sale completing" (CN-002, USD 4.2m, CL-0002) is flagged as contingent on an event that itself generates liquidity; Aspirational excluded.
14. **Add near-term escalation:** a Confirmed need with `due_from` within 6 months and Daily-cash cover < 1.0x escalates regardless of the 12-month ratios. (Otherwise Margarethe — bill due in five weeks — only "warns".)
15. **Cash definition:** split Daily cash from term deposits. USD 9.0m of book "cash" is 3M SGD fixed deposits at Monthly tier across six clients; Tan Boon Huat's entire USD 2.37m of "cash" is one term deposit. FDs stay in the 12-month test; the near-term test uses Daily cash only; client-facing wording is "cash and short-term deposits".

### Collateral (Module 4)

16. **Prose correction:** CF-0002 did NOT rise at every snapshot (53.93 → 53.53 Dec→Feb). Say "risen at three consecutive observations since February" — the trend criterion still fires.
17. **Add the fragile-cure sub-flag:** facility that (a) breached at an earlier snapshot, (b) cured with no reduction in drawn (CF-0005 drawn flat at 8.0m throughout — verified), (c) collateral recovery concentrated in instruments on an unresolved event-log channel. Without it CF-0005 — the demo's cured-by-geopolitics story — produces no alert today.

### Look-through (Module 5)

18. **Add the hidden-exposure trigger:** any single-issuer look-through exposure ≥ 10% of household with ZERO direct holding fires as informational, regardless of the limit. (Al-Mansoori's 12.9% Bara and Kim's 12.8% Helios — the section's own headline findings — are below their limits and never fire under the frozen threshold.)
19. **Terminology:** attribution is per-name full current MARKET VALUE of the note, not "notional"; cross-issuer rows double-count and must never be summed.
20. **Accumulator correction:** SYN-SP-0503 accumulates daily at HKD 17.20 with double-up below strike, and the stock is 24% below strike — market-value attribution UNDERSTATES Lau's forward exposure. Flag as understated; action item: obtain remaining accumulation notional from the term sheet. Delete/qualify "deliberately conservative" for this instrument.
21. **Generalize the issuer map:** issuer defaults to the instrument itself for every `concentration_limit_applies='Y'` instrument; the curated same-issuer table overrides. Concretely missed today: Lau holds 17.6% of household in Pacific Rim Bank's perpetual vs his 12% tightest limit; Chalermchai 11.4% in the same paper.
22. **SYN-SP-0506 disclosure:** its "three Asian banking majors" are unnamed and unscreenable — the alert must say so rather than show a clean zero.

### Belief gap (Module 6)

23. **Fix the 9/9 overclaim:** six pairs contradicted; two notes (N-010 waiver, N-021 — Yamamoto is recorded as AWARE of the yen mismatch) are constraints/corroborations; one (N-028) is an unanswered question. Reword the frozen table.
24. **Reframe the Hartono pair:** his 41.4% coal stake is 98% of his CUSTODY account — the legacy holding he said he cannot reduce (N-001). The pair that survives: "Your managed portfolio was the non-mine part — until the April FCN you asked for (N-002) put 6.2% of it into the same trade; the whole relationship is 45% energy and shipping."
25. **Cheung/Chalermchai pairs must show income received** next to the mark-to-market fall (Cheung: −2.48m marks vs +1.15m income; Chalermchai: −2.2m vs +1.55m).
26. **Add the Elena Marchetti-Wong pair (N-024):** "sized gold as a 5% hedge" vs 14.04% today and above the 10% mandate max; her business and largest equity holding are the same Greater-China-luxury bet. Consider Lindqvist N-013 as well.
27. **Presentation rule:** "You said" renders as "as recorded in RM note N-xxx of <date>" — RM paraphrase, not verbatim client speech; RM review before client use (keep the frozen manual-pairing governance).

### Event / currency / suitability (Module 7)

28. **Event channel map becomes a versioned, human-reviewed artifact** covering every `primary_transmission` value (duration, tech/collateral, private-credit and gold channels included — not just the Strait), each alert citing event row id + mapping version.
29. **Event alerts carry direction** (Hartono/Al-Mansoori lose on REOPENING; bond holders lose on escalation) and disclose the Broad Commodity Index full-weight approximation.
30. **Currency mismatch — implement the promised weighting:** informational at >40% non-base; escalate only with a confirmed base-ccy need within 24 months or a base-ccy income/decumulation objective; disclose "assumed unhedged". (Bare >40% fires on 7 of 20 clients — wallpaper.)
31. **Suitability drift definition = threshold:** score ≤ 3 AND (base-ccy period return < −5% OR max drawdown across snapshots < −7%); drop "realised volatility" (uncomputable from five points); show income received alongside.

### Demo narrative (Module 8)

32. **All client-facing performance numbers switch to ex-new-position (same-store) returns:** Al-Mansoori +9.7% (not +25.9%), Kim +9.2% (not +25.3%), Hartono +19.0% (not +23.4%), Zhang +10.2% (not +18.6%). The inversion story survives; the printed numbers violate the notebook's own Decision 3.
33. **Al-Mansoori:** replace "entirely from a conflict" with the computed split (strait names ≈ +2.3m on 7.5m held from the start; rest of book ≈ +2.3pp).
34. **Margarethe:** selling EUR 3.4m of equity leaves her at 65.7% equity — still ~35pp over cap; full cure ≈ a further EUR 8.4m into fixed income. Frame the tax sale as tranche one of a glide path; re-solicit the N-005 "no changes" instruction; attach the tax-lot remediation action.
35. **Lau:** add that HKD 4m of the facility draw funded accumulator settlements (N-018) — the LTV climb partly finances the bleed — and the 17.6% Pacific Rim perpetual stack.

---

## 3. What I verified independently (numbers I got from raw data)

- **DQ-01:** 1 of 206 positions ever changes quantity (PF-0009 gold 6,000→8,000); 6 appear; 0 vanish. New positions at 2026-08-26 = USD 13.80m + 0.85m gold increment = **14.66m** (notebook: "14.7m" ✓). Purchase cost ≈ USD 15.34m.
- **Book:** 577.20m → 596.22m (+3.30%) ✓ across the five snapshots.
- **Base vs USD returns:** CL-0009 −4.02% USD / +1.96% EUR ✓; CL-0003 −5.68% / +0.19% ✓. All 24 portfolio base currencies match their client's base currency (household base sums are safe).
- **Mandate:** 14 band breaches / 9 clients, reproduced with an independent full-grid method ✓. CL-0003: 71.46% equity vs 10–30 band, 9.15% FI vs 45% floor ✓. Mandate table complete (8 codes × 6 classes). **13 per-portfolio single-position breaches** (not in the notebook's frozen signal). SUSBAL exclusions 21.30% ✓.
- **Funding gap:** Margarethe CN-004 EUR 3.4m Confirmed, Oct–Dec 2026; cash cover 0.46x ✓; daily 5.27x. **CN-016 = COM-001+COM-002 exactly (15.8m); CN-008 = COM-003 exactly (3.0m)** — double-counted. Corrected: CL-0017 0.32x/3.27x; CL-0006 0.26x/1.56x. "Nine of twenty below 1.0x cash cover" survives dedupe ✓. USD 9.0m of "cash" is 3M fixed deposits (Monthly tier).
- **Collateral:** recomputed lending value from holdings advance rates for all 5 facilities × 5 snapshots — **matches `credit_facilities.csv` to the dollar**; implied drawn matches drawn columns. LTV histories match the notebook table exactly. CF-0005 drawn flat at 8.0m throughout (cure was 100% market). CF-0002 fell Dec→Feb before rising three consecutive observations.
- **Look-through:** Hartono 41.4+3.6=45.0 ✓ (Bara is 98% of custody PF-0002); Lau 9.5+12.9+7.0=29.5 ✓; Al-Mansoori 11.4+12.9=24.3 ✓ and 12.9 Bara with zero direct ✓; Zhang 15.4+7.1=22.5 ✓; Kim 12.8 ✓. Tightest limits 15/12/15/15/20 ✓; custody mandates never set the binding minimum. Lau also 17.6% Pacific Rim perpetual (unmapped issuer). Lau instrument falls −41.7/−31.1/−24.2 ✓.
- **Event/currency/suitability:** Strait exposures 45.0/42.1/20.4 ✓; non-base shares 97.1/72.1/61.3/56.4 ✓ with **7 clients >40%**; suitability drift fires on exactly CL-0004 (−6.61%) and CL-0012 (−6.98%), both score 3; max drawdowns −7.6/−8.2%.
- **Income (from transactions):** CL-0012 +1.15m; CL-0004 +1.62m raw (≈1.55m at today's FX), annualising ≈ 2.4m vs his 1.45m/yr requirement.
- **Same-store client returns (my computation):** Al-Mansoori +9.7% / Kim +9.2% / Hartono +19.0% / Zhang +10.2% vs headline 25.9/25.3/23.4/18.6.
- **KYC:** contrary to the data dictionary's "some are overdue", **none is overdue** at 2026-08-26; earliest is CL-0011 on 2026-08-31 (five days). Worth flagging openly per the README's "say so" instruction.
- **RM notes:** read all 28 in full; quotes used in the pairs are faithful to the note text; N-026 "We have not modelled this" is verbatim.

---

## 4. Are these the right 8 signals?

Keep all eight; the ranking is broadly right (mandate first, funding second, collateral third is exactly how a committee would order defensibility). A veteran would add or fold in:

1. **Stale-mark concentration (promote DQ-05 into a signal):** valuation age > 2 quarters AND position > 25% of household → alert. It is CL-0002's dominant fact and today lives only in a caveat. Cheap: the valuation-age field is already a preprocessing decision.
2. **Tax awareness (at minimum a fact, if not a signal):** unrealised gains/losses side-by-side per household filtered by `tax_domicile` (Germany, UK, Japan, Italy clients have CGT exposure; Singapore/HK largely do not). The challenge brief names tax-aware optimisation; the shortlist is silent. Pemberton-Hale's N-011 ("fund the foundation from appreciated assets… UK tax questions unresolved") is a ready-made story.
3. **Unactioned commitments/questions from notes:** N-028 (client question unanswered 1 week), N-022 (liquidity map promised for the October IC). Trivial to surface, enormous RM value — this is the "who to call first" feature the README asks for.
4. **KYC/review dates:** not a market signal, but the first thing an auditor checks in a prioritisation product. CL-0011 in five days.

If forced to rank the existing eight again, I would swap 6 and 5: event exposure (auditable, thresholded, scenario-linked) is more defensible in front of compliance than the manually-paired belief gap, however good the demo value of the latter.

---

## 5. Open risks

1. **The income blind spot is systemic.** Every "return" in this analysis is price-only. Fine for a synthetic dataset where cash never moves; commercially wrong in front of Income-mandate clients. The pipeline must carry income as a first-class fact or the product will lose its first meeting with a bond client.
2. **Threshold provenance.** Several thresholds (10pp escalation, 1.5x daily, 5pp LTV proximity, 15% channel, 40% currency) were chosen "after seeing the distribution" — i.e., fitted to n=20. Defensible for a demo; a committee would want them restated as policy choices with rationale, and the write-up should say which they are.
3. **Hand-curated maps (issuer map, channel map, look-through map) are single points of failure.** All three must ship as versioned, reviewed artifacts, or every derived signal inherits an unauditable step.
4. **The worst-of full-value attribution can exceed 100% of household when summed across issuers.** The caveat exists; the UI must enforce non-summation or someone will put a 130% pie chart in front of a client.
5. **Scenario rehearsal (Strait reopening) is promised by the narrative but not specced by any signal.** Modules 4/7 changes (fragile-cure flag, direction field) give it hooks; the actual reshock math is still undesigned at Phase A close. That is acceptable for Phase A but is the largest unbuilt promise.
6. **Dictionary-vs-data discrepancies** (KYC "overdue", private marks "one quarter behind" vs 11 months) should be disclosed in the presentation — noticing is worth points; silence looks like blindness.

---

## 6. Overall grade (as a first-year associate)

**A−.**

What earns it: the data verification discipline is genuinely excellent — reconciliation of holdings to AUM to the cent, the advance-rate lending-value reconstruction, the holdings-vs-transactions structural finding, and the custody/look-through/household treatments are things I have seen second-year analysts at real banks get wrong. The three demo clients are the right three. The writing explains itself to a non-finance reader, which the product requires. Section 11 is the best part of the notebook: it found the planted imperfections and, more importantly, understood their consequences.

What keeps it off an A: the analysis breaks its own best rule. Having proven that new positions are not performance, it then quotes four client returns that include them — and builds the flagship client story on the most inflated of the four. Add the funding-gap double-count (a family office CFO catches USD 15.8m counted twice in one meeting), the price-only "loss" numbers aimed at income clients, and the "all nine contradicted" overclaim, and the pattern is clear: the associate is superb at interrogating the data and still learning to interrogate their own conclusions with the same severity. Every one of these was findable with the notebook's own tools in under an hour.

Nothing here is unsound in architecture; everything required is a correction, not a redesign. Implement the 35 changes above and this shortlist would pass the suitability committee I used to sit on.
