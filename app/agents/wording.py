"""Constrained conversation prompts, not authority to trade or assertions of suitability."""

OPENING = "May we review your priorities and the portfolio findings together?"
ALTERNATE_OPENING = "Could we start by discussing your priorities for this meeting?"
PRIORITIES_QUESTION = "What would you most like us to clarify today?"

DISCUSSION_QUESTIONS = {
    "mandate_gap": (
        "Has your willingness to change the portfolio changed since our last discussion?"
    ),
    "deadline": "Which assets should we review for the upcoming payment, before deciding to sell?",
    "change": "Would you like to review the holding changes and the associated event evidence?",
    "facility": "Should we review collateral headroom before discussing any additional borrowing?",
    "concentration": "Does this concentration still fit your intended diversification?",
}


def rationale(fact_text: str, passage_text: str | None, *, dataset_note: bool) -> str:
    if passage_text and dataset_note:
        return (
            f'Data says: {fact_text} RM note records: "{passage_text}" '
            "Confirm current intent before considering changes."
        )
    if passage_text:
        return f'Ask how this relates to the client statement: "{passage_text}"'
    return "Ask the client how this finding relates to their current priorities."
