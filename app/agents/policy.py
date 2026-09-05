"""Deterministic selection and evidence-bound private-banking discussion policy."""

from app.agents.contracts import (
    Claim,
    CuratedClientBundle,
    InformationRequest,
    Signal,
    fingerprint,
)
from app.agents.phase_a import LIMITATIONS
from app.agents.wording import rationale

QUESTIONS = {
    "mandate_band_breach": (
        "Which mandate constraints and current client instructions should the Relationship "
        "Manager confirm before discussing allocation changes?"
    ),
    "mandate_single_position_breach": (
        "Should the Relationship Manager review the position against its managed Portfolio "
        "limit and obtain current written instructions?"
    ),
    "mandate_exclusion_breach": (
        "Who will reconcile the binding exclusion and document remediation? An RM note "
        "does not establish an override or approval."
    ),
    "funding_gap": (
        "Which obligations have confirmed timing, and which unencumbered assets could "
        "settle in the required currency before payment?"
    ),
    "lookthrough_concentration": (
        "How does direct and structured-product issuer exposure compare with each managed "
        "Mandate, and which product terms require confirmation?"
    ),
    "lookthrough_unavailable": (
        "Can the product specialist supply complete basket constituents and the current "
        "term sheet before assessing issuer exposure?"
    ),
    "accumulator_forward_exposure": (
        "Can the product specialist confirm remaining accumulation notional, double-up "
        "obligations and termination terms before discussing forward exposure?"
    ),
    "collateral_stress": (
        "Should the Relationship Manager confirm collateral eligibility, repayment options "
        "and linked cash obligations before discussing additional borrowing?"
    ),
    "currency_mismatch": (
        "Which payment currencies and documented hedges should the Relationship Manager "
        "confirm before discussing currency alignment?"
    ),
    "event_exposure": (
        "Which mapped event channels overlap the Client's holdings and source of wealth, "
        "and which assumptions need confirmation?"
    ),
    "suitability_drift": (
        "Has the Client's ability or willingness to bear loss changed, and should the "
        "Relationship Manager refresh the suitability review?"
    ),
}

QUALITY_ACTIONS = {
    "PHASE_A_HOLDINGS_UNAVAILABLE": (
        "Request an eligible holdings statement from the custodian.",
        "Holdings are unavailable; absent positions do not establish zero wealth.",
        "Custodian",
        ["current wealth", "current allocation"],
    ),
    "PHASE_A_STALE_SNAPSHOT": (
        "Request the latest holdings statement and confirm current availability.",
        "The supplied holdings snapshot is stale; current availability and values are unconfirmed.",
        "Custodian",
        ["current valuation", "current funding availability"],
    ),
    "PHASE_A_MISSING_COST_BASIS": (
        "Request original purchase records and validated tax-lot cost basis.",
        (
            "Missing cost basis leaves unrealised profit and loss incomplete and disposal "
            "tax unestablished."
        ),
        "Custodian or tax adviser",
        ["complete unrealised profit and loss", "disposal tax"],
    ),
    "PHASE_A_MATERIAL_STALE_VALUATION": (
        "Request a current independent valuation and executable exit or redemption terms.",
        (
            "A materially stale valuation is not a current executable price or reliable "
            "exit-liquidity estimate."
        ),
        "Valuation provider",
        ["current executable price", "exit liquidity"],
    ),
    "PHASE_A_UNKNOWN_SECTOR": (
        "Request the missing sector classification and retain the unknown exposure bucket.",
        "Unknown sector classifications prevent a complete sector exposure assessment.",
        "Instrument data owner",
        ["complete sector exposure"],
    ),
    "PHASE_A_NONDAILY_CASH": (
        "Confirm deposit maturity, withdrawal restrictions and settlement timing.",
        "Non-Daily cash and deposits are not established as immediately available funding.",
        "Custodian",
        ["immediate deposit availability"],
    ),
    "PHASE_A_LEDGER_UNAVAILABLE": (
        "Request the complete settled transaction and cash ledger, including income and fees.",
        "The ledger is unavailable; income and fees are unknown rather than established as zero.",
        "Custodian",
        ["complete income and fees", "validated total return"],
    ),
    "PHASE_A_TRANSFER_TAX_BASIS_UNVERIFIED": (
        (
            "Request original purchase or inherited tax-lot history from the transferring "
            "institution or estate executor."
        ),
        (
            "Transferred book bases do not establish original or inherited tax-lot bases "
            "for disposal-tax advice."
        ),
        "Transferring institution or estate executor",
        ["disposal tax", "validated tax-lot basis"],
    ),
    "PHASE_A_LEDGER_UNRECONCILED": (
        (
            "Request reconciliation of holdings, transactions and the complete cash "
            "ledger, including income and fees."
        ),
        (
            "The ledger is unreconciled; reported mark changes and separate receipts or "
            "payments are not validated total return."
        ),
        "Custodian",
        ["validated total return", "transaction-based holdings roll-forward"],
    ),
    "PHASE_A_INCOMPLETE_MANDATE_TARGET": (
        (
            "Request an approved complete target allocation while retaining supported "
            "mandate-band checks."
        ),
        "The mandate target allocation is incomplete; target-based rebalancing is underdefined.",
        "Mandate owner",
        ["target-based rebalancing"],
    ),
    "PHASE_A_PURCHASE_BASIS_MISMATCH": (
        "Request reconciliation of purchase records and reported cost or tax basis.",
        (
            "Purchase quantities may reconcile while the reported cost or tax ledger "
            "remains inconsistent."
        ),
        "Custodian or tax adviser",
        ["validated cost basis", "disposal tax"],
    ),
    "PHASE_A_FACILITY_ACTIVITY_UNRECONCILED": (
        (
            "Request complete drawdown, repayment and other facility activity records and "
            "reconcile them to reported balances."
        ),
        (
            "Facility activity is unreconciled; missing repayments or other activity do "
            "not establish use of proceeds."
        ),
        "Credit operations",
        ["reconciled facility activity", "use of proceeds"],
    ),
}

SIGNAL_ACTIONS = {
    "lookthrough_unavailable": (
        "Request complete basket constituents and the current term sheet.",
        "Unknown basket constituents are unscreenable, not zero issuer exposure.",
        "Product specialist",
        ["complete issuer exposure", "complete event exposure"],
    ),
    "accumulator_forward_exposure": (
        "Request remaining accumulation notional, double-up obligations and termination terms.",
        (
            "Current product value does not establish forward accumulation obligations or "
            "maximum loss."
        ),
        "Product specialist",
        ["forward accumulation exposure", "maximum loss"],
    ),
}

SIGNAL_DISCLOSURES = {
    "mandate_band_breach": (
        "Confirm current written mandate instructions and any waiver scope. RM notes do "
        "not establish a current waiver, approval or cause of the breach."
    ),
    "mandate_single_position_breach": (
        "Confirm current written mandate instructions and any waiver scope. RM notes do "
        "not establish a current waiver, approval or cause of the breach."
    ),
    "mandate_exclusion_breach": (
        "A binding exclusion requires reconciliation and documented remediation; RM notes "
        "do not establish an override or approval."
    ),
    "funding_gap": (
        "Funding resources are gross screens. Confirm encumbrance, execution costs, "
        "settlement, currency conversion and tax before treating assets as available cash."
    ),
    "lookthrough_concentration": (
        "Issuer look-through uses non-additive current product market values, not "
        "derivative notional, maximum loss or a household compliance determination."
    ),
    "lookthrough_unavailable": SIGNAL_ACTIONS["lookthrough_unavailable"][1],
    "accumulator_forward_exposure": SIGNAL_ACTIONS["accumulator_forward_exposure"][1],
    "collateral_stress": (
        "Observed collateral recovery does not establish durable headroom or a calibrated "
        "future stress outcome. Confirm facility terms and linked funding obligations."
    ),
    "currency_mismatch": (
        "Currency exposure is assumed unhedged unless a hedge is documented; a mismatch "
        "screen does not establish a trade instruction."
    ),
    "event_exposure": (
        "Event channels overlap and are non-additive. Associations do not establish "
        "causation, a calibrated loss scenario or hedge effectiveness."
    ),
    "suitability_drift": (
        "Reported mark changes are not reconciled total return. A suitability screen "
        "requires Relationship Manager review and does not establish unsuitability."
    ),
}


def selected_signals(bundle: CuratedClientBundle) -> list[Signal]:
    """Preserve score precedence and diversify equal-score conversation families."""
    selected = []
    signatures: set[tuple[str, ...]] = set()
    families: set[str] = set()
    event_channels: set[str] = set()
    remaining = sorted(bundle.signals, key=lambda item: (-item.score, item.id))
    while remaining and len(selected) < 3:
        highest_score = remaining[0].score
        tier = [signal for signal in remaining if signal.score == highest_score]
        signal = next(
            (candidate for candidate in tier if _family(candidate) not in families), tier[0]
        )
        remaining.remove(signal)
        signature = tuple(sorted(signal.fact_ids))
        channel = signal.metadata.get("channel") if signal.kind == "event_exposure" else None
        if signature in signatures or (channel and channel in event_channels):
            continue
        selected.append(signal)
        signatures.add(signature)
        families.add(_family(signal))
        if channel:
            event_channels.add(channel)
    return selected


def _family(signal: Signal) -> str:
    if not signal.kind:
        return signal.id
    return "mandate" if signal.kind.startswith("mandate_") else signal.kind


def discussion_question(signal: Signal) -> str | None:
    return QUESTIONS.get(signal.kind)


def discussion_point(signal: Signal, first_fact_text: str) -> str:
    question = discussion_question(signal)
    return f"{first_fact_text} {question}" if question else f"Discuss: {first_fact_text}"


def signal_rationale(
    signal: Signal, fact_text: str, passage_text: str | None, *, dataset_note: bool
) -> str:
    if not signal.kind:
        return rationale(fact_text, passage_text, dataset_note=dataset_note)
    prompt = (
        discussion_question(signal)
        or "Confirm the source finding and current Client intent with the Relationship Manager."
    )
    if passage_text:
        source = "RM note records" if dataset_note else "Client statement records"
        return (
            f'{prompt} {source}: "{passage_text}" Confirm current intent; '
            "the statement is not an approval or instruction to trade."
        )
    return prompt


def _quality_groups(bundle: CuratedClientBundle) -> list[tuple[str, str, list[str]]]:
    groups: dict[tuple[str, str], set[str]] = {}
    for finding in bundle.quality_findings:
        key = (finding.code, finding.portfolio_id or "client")
        groups.setdefault(key, set()).update(finding.evidence_ids)
    return [
        (code, scope, sorted(references)) for (code, scope), references in sorted(groups.items())
    ]


def _quality_action(code: str) -> tuple[str, str, str, list[str]]:
    return QUALITY_ACTIONS.get(
        code,
        (
            "Request source-owner clarification and corrected or complete supporting records.",
            (
                "An unresolved Data Quality Finding limits conclusions based on the "
                "affected Source Records."
            ),
            "Source data owner",
            ["conclusions dependent on the affected records"],
        ),
    )


def expected_information_requests(bundle: CuratedClientBundle) -> list[InformationRequest]:
    entries = [
        (f"quality:{code}:{scope}", code, citations, _quality_action(code))
        for code, scope, citations in _quality_groups(bundle)
    ]
    entries.extend(
        (f"signal:{signal.id}", signal.kind, signal.fact_ids, SIGNAL_ACTIONS[signal.kind])
        for signal in sorted(bundle.signals, key=lambda item: item.id)
        if signal.kind in SIGNAL_ACTIONS
    )
    return [
        InformationRequest(
            id=f"information:{identifier}",
            code=code,
            request=Claim(
                id=f"request:{identifier}", text=action[0], citations=citations, kind="suggestion"
            ),
            reason=Claim(
                id=f"reason:{identifier}", text=action[1], citations=citations, kind="uncertainty"
            ),
            owner=action[2],
            blocked_conclusions=action[3],
        )
        for identifier, code, citations, action in entries
    ]


def expected_disclosures(bundle: CuratedClientBundle) -> list[Claim]:
    disclosures = []
    if (
        bundle.pipeline_run_id
        or any(
            not fact.formula_id.startswith(("legacy.", "fixture.legacy.")) for fact in bundle.facts
        )
        or any(signal.kind for signal in bundle.signals)
    ):
        disclosures.append(
            Claim(
                id="disclosure:phase_a",
                text=LIMITATIONS,
                citations=[bundle.facts[0].id],
                kind="uncertainty",
            )
        )
    for code, scope, citations in _quality_groups(bundle):
        disclosures.append(
            Claim(
                id=f"disclosure:quality:{code}:{scope}",
                text=_quality_action(code)[1],
                citations=citations,
                kind="uncertainty",
            )
        )
    grouped: dict[str, set[str]] = {}
    for signal in bundle.signals:
        wording = SIGNAL_DISCLOSURES.get(signal.kind)
        if wording:
            grouped.setdefault(wording, set()).update(signal.fact_ids)
    for wording, citations in sorted(grouped.items()):
        disclosures.append(
            Claim(
                id=f"disclosure:signal:{fingerprint(wording)[:16]}",
                text=wording,
                citations=sorted(citations),
                kind="uncertainty",
            )
        )
    return disclosures
