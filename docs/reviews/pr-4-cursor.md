# PR 4 review decisions

Reviewed the eight inline comments and the full review posted by Tien-Cheng on [PR 4](https://github.com/choiwab/SingHacks-2026/pull/4), plus the separate Copilot comment.
The current branch was clean at the start of this review.

## Inline comments

| Original location | Decision | Result or reason |
| --- | --- | --- |
| ClientDashboard.tsx:43, severity table | Addressed | Removed the severity table and all frontend severity assignments. |
| ClientDashboard.tsx:329, confidence to data health | Addressed | Shows data health as unavailable; confidence is preserved on the individual facts and never presented as freshness. |
| ClientDashboard.tsx:754, insight sorting | Addressed | Shows non-profile facts in supplied order, with three preview cards and the remainder in Insights; labels them Client facts rather than ranked insights. |
| ClientDashboard.tsx:1152, commitment reconstruction | Addressed | Removed source-row joins and sorting; Planned cash needs renders deadline facts directly, with raw source details available through Evidence. |
| evidence.tsx:308, terminology | Addressed | Missing-evidence copy and the accessible list name now say source records. |
| Home.tsx:183, landing queue | Ignored | The cited acceptance criterion permits one interaction; selecting Margarethe from the queue or switcher opens her profile, facts, and meeting brief in one click, and client selection directly serves the specified workflow. |
| Scenario.tsx:110, rewritten disclaimer | Addressed | The visible disclaimer, accessible chart description, announcement, and evidence all preserve the projection disclaimer verbatim. |
| PreRead.tsx:273, Fluent styling | Addressed | Removed the independent palette and font stack; headings, cards, checkpoint text, and notifications use Fluent components or tokens, with layout CSS retained. |

The `.client-heading` claim was partly stale: the selected-client header was already a dedicated component, and the remaining class was a wrapper.
The palette and typography criticism was valid regardless, and that wrapper now only controls layout.

## Broader standards findings

- **Projection rules in the browser:** accepted, including the summary's observations about locally authored questions, financial prose, summary assembly, and Changed/Unchanged inference.
  Removed those fallbacks rather than duplicating the upstream team's responsibilities.
  A visible disclosure identifies briefing fields that the current projection does not provide.
- **Fluent styling and Evidence terminology:** accepted and addressed as above.
- **Divergent responsibilities in ClientDashboard:** partly accepted.
  Removing domain decisions and briefing synthesis substantially reduces the module; existing rendering and local search remain together without adding a speculative abstraction layer.
- **Duplicated constants and formatting:** accepted.
  `presentation.ts` now owns the shared urgency appearance, narrow breakpoint, and value formatter.
- **Repeated fact-kind switches:** addressed by removing severity, advisory prose, and question generation.
  The remaining measure switch maps supplied values to chart coordinates and labels, which is the PRD's permitted financial visualization work.
- **Evidence prop group:** ignored.
  Explicit typed props make each claim's client, evidence, and review state visible, and the existing EvidenceRequest already groups them at the drawer boundary.
  Replacing them with another object would not correct behavior or reduce independent state.
- **Ambiguous stake name:** addressed by removing the function together with its unsupported generated prose.

## Broader specification findings

- **Initial selected-client screen / home priority queue:** ignored as a requested removal for the one-interaction reason above.
  The home queue displays backend ranking, unlike the removed frontend fact ranking.
- **Meeting purpose, refresh time, generation time, and Updating:** valid integration gaps.
  The header explicitly distinguishes the snapshot date, missing purpose, unavailable timestamps, and unavailable health.
  There is no live update operation or supplied health field from which to render Updating truthfully.
- **Memory promises, preferences, and concerns:** valid upstream gap, not a frontend extraction task.
  The current contract supplies chronological notes and extracted beliefs; inventing additional categories in React would violate the same ownership requirement.
- **Suggested questions / opening mislabeled as a question:** accepted.
  The supplied text is now labeled Suggested opening in both views; independent questions and discussion topics are disclosed as unavailable.
- **New / Changed / Unchanged after updates:** valid upstream integration gap.
  Removed inferred version-state badges because snapshot changes do not establish insight-version changes.
  Connecting the controlled update requires the Member 4 API and versioned view model.
- **Dedicated scenario route:** ignored as a requested removal.
  The PRD explicitly permits precomputed scenario ranges; this existing optional route supports conversation preparation and does not interrupt the required review flow.
- **Rules & money and Where you left off:** ignored as requested removals.
  Both display existing cited pre-read content useful for understanding discrepancies and remembering the prior conversation, satisfying the final scope rule even though their titles are not enumerated in section 5.5.
- **Frontend ranking, health, prose, summary, topics, and update inference:** accepted and removed as detailed above.
- **Cards claiming ranked personalized insights:** accepted.
  Cards now identify themselves as facts and display supplied headlines, confidence, cited uncertainty, and permitted visualizations without invented severity or advice.
- **Scenario wording:** accepted and fixed verbatim.

These decisions intentionally leave missing backend capabilities visible rather than claiming the full PRD has been implemented.
No backend contract or generated file was changed.

## Separate Copilot comment

Ignored the request to move the guarded route reset into an effect.
The state update targets the same component and is conditional on a changed pathname, so the next render terminates the reset.
The reported cross-component render warning was not reproduced.
The existing history tests verify immediate drawer dismissal, client isolation, focus behavior, and no reopening on forward navigation.
An effect is not required to correct that behavior.

## Validation

The running app reproduced the original severity, health, commitments, and scenario wording issues before edits.
Manual checks use chrome-devtools-axi, with desktop and narrow-window screenshots.
Automated browser checks also exercise 320px and 390px layouts.
Regression coverage checks source order, unavailable health even for low-confidence or missing facts, missing briefing fields, cash-need evidence, exact scenario disclaimers, and the existing navigation and review flows.

Final validation passes: 104 browser tests with no retries or skips, 23 component tests, and 24 Python tests.
Frontend and Python lint, formatting, type checks, generated-contract verification, and the production build pass.
The Memory component test exercises keyboard activation; browser tests retain pointer activation coverage.
No PR comments were posted or threads resolved remotely during this review.
