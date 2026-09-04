import {
  Badge,
  Body1,
  Button,
  Body1Strong,
  Caption1,
  Subtitle2,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";

import type {
  ClientPreRead,
  MondayBriefProjection,
  ProjectionFact,
  RankedClient,
} from "./contracts";
import { useNavigate } from "react-router-dom";

import type { Authorship } from "./evidence";
import { WhyButton } from "./shared";

/**
 * Insight severity per deterministic fact kind (PRD 5.4). The pipeline does not
 * emit a severity field yet, so the ordering lives here.
 * ponytail: move to the projection once the fact engine ranks its own output.
 */
const SEVERITY: Record<
  ProjectionFact["kind"],
  { rank: number; label: string; color: "danger" | "warning" | "informative" }
> = {
  mandate_gap: { rank: 0, label: "High", color: "danger" },
  deadline: { rank: 1, label: "High", color: "danger" },
  concentration: { rank: 2, label: "Medium", color: "warning" },
  facility: { rank: 3, label: "Medium", color: "warning" },
  change: { rank: 4, label: "Low", color: "informative" },
  profile: { rank: 5, label: "Context", color: "informative" },
};

const FACT_GROUP: Record<ProjectionFact["kind"], string> = {
  profile: "Profile",
  mandate_gap: "Mandate",
  deadline: "Cash need",
  facility: "Collateral",
  concentration: "Concentration",
  change: "Snapshot change",
};

/** Matches the shell breakpoint where the client switcher becomes a strip. */
const NARROW = "@media (max-width: 60rem)";

const useStyles = makeStyles({
  header: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "flex-start",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalXXL,
    rowGap: tokens.spacingVerticalM,
    paddingBlockEnd: tokens.spacingVerticalL,
  },
  headerMain: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXS,
    flexGrow: 1,
    flexShrink: 1,
    flexBasis: "26rem",
  },
  headerSide: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: tokens.spacingVerticalXS,
    flexGrow: 0,
    flexShrink: 1,
    flexBasis: "19rem",
  },
  chips: {
    display: "flex",
    flexWrap: "wrap",
    gap: tokens.spacingHorizontalXS,
    listStyleType: "none",
    ...shorthands.margin(tokens.spacingVerticalXS, 0, 0),
    ...shorthands.padding(0),
  },
  panel: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalL,
    paddingBlock: tokens.spacingVerticalL,
  },
  cards: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(17rem, 1fr))",
    gap: tokens.spacingHorizontalM,
  },
  card: {
    display: "flex",
    // Keeps a lone card readable instead of stretching it across the dashboard.
    maxWidth: "34rem",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
    ...shorthands.padding(tokens.spacingVerticalM, tokens.spacingHorizontalM),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  cardMeta: {
    display: "flex",
    flexWrap: "wrap",
    gap: tokens.spacingHorizontalXS,
  },
  numbers: {
    display: "grid",
    gridTemplateColumns: "auto 1fr",
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalXXS,
    ...shorthands.margin(0),
  },
  term: {
    color: tokens.colorNeutralForeground3,
    fontSize: tokens.fontSizeBase200,
    textTransform: "capitalize",
  },
  value: {
    ...shorthands.margin(0),
    fontSize: tokens.fontSizeBase200,
    fontVariantNumeric: "tabular-nums",
  },
  group: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
  },
  note: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
    paddingInlineStart: tokens.spacingHorizontalM,
    borderInlineStartWidth: "2px",
    borderInlineStartStyle: "solid",
    borderInlineStartColor: tokens.colorNeutralStroke2,
  },
  headerActions: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: tokens.spacingHorizontalS,
    marginBlockStart: tokens.spacingVerticalXS,
  },
  action: {
    alignSelf: "flex-start",
  },
  empty: {
    color: tokens.colorNeutralForeground3,
  },
  calendar: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXS,
    paddingBlockEnd: tokens.spacingVerticalL,
  },
  strip: {
    display: "flex",
    flexWrap: "wrap",
    gap: tokens.spacingHorizontalS,
    listStyleType: "none",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
    // Narrow windows scroll the week sideways, like the client strip above it,
    // rather than pushing the client name below the fold.
    [NARROW]: { flexWrap: "nowrap", overflowX: "auto" },
  },
  meeting: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: "2px",
    minWidth: "13rem",
    cursor: "pointer",
    textAlign: "left",
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke2),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    ...shorthands.padding(tokens.spacingVerticalS, tokens.spacingHorizontalM),
    backgroundColor: tokens.colorNeutralBackground1,
    ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  meetingSelected: {
    ...shorthands.borderColor(tokens.colorBrandStroke1),
    backgroundColor: tokens.colorBrandBackground2,
  },
  meetingWhen: {
    color: tokens.colorNeutralForeground3,
    fontVariantNumeric: "tabular-nums",
  },
  summary: {
    maxWidth: "68ch",
    ...shorthands.margin(0),
  },
  topics: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalL,
    listStyleType: "none",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
  },
  topic: {
    // Fluent Text renders inline; the column makes each line its own row.
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: tokens.spacingVerticalXS,
  },
});

function formatNumber(value: unknown) {
  if (typeof value === "number")
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (value === null || value === undefined) return "Not recorded";
  return String(value);
}

function FactNumbers({ fact }: { fact: ProjectionFact }) {
  const styles = useStyles();
  return (
    <dl className={styles.numbers}>
      {Object.entries(fact.numbers).map(([key, value]) => (
        <div key={key} style={{ display: "contents" }}>
          <dt className={styles.term}>{key.replaceAll("_", " ")}</dt>
          <dd className={styles.value}>{formatNumber(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Data health is derived from the confidence the fact engine reported, so the
 * header never claims more certainty than the pipeline produced (PRD 5.2).
 */
function dataHealth(facts: ProjectionFact[]) {
  if (facts.some((fact) => fact.confidence === "low"))
    return { label: "Needs confirmation", color: "warning" as const };
  if (facts.length === 0) return { label: "Stale", color: "danger" as const };
  return { label: "Current", color: "success" as const };
}

type FactOf<K extends ProjectionFact["kind"]> = Extract<
  ProjectionFact,
  { kind: K }
>;

const factOfKind =
  <K extends ProjectionFact["kind"]>(kind: K) =>
  (fact: ProjectionFact): fact is FactOf<K> =>
    fact.kind === kind;

function formatMoney(amount: number, currency: string | null | undefined) {
  const rounded = Math.round(amount);
  if (!currency) return formatNumber(rounded);
  return rounded.toLocaleString(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  });
}

/**
 * The quantified stake behind a fact, in one line. The Overview ledger states
 * what the fact is; an agenda item has to say how much of it there is, so this
 * reads the calculation inputs the fact engine already emitted.
 */
function stake(fact: ProjectionFact, currency?: string): string {
  switch (fact.kind) {
    case "mandate_gap": {
      const n = fact.numbers;
      return `${n.asset_class} sits at ${n.actual_pct}% against a ${n.limit_pct}% ${n.boundary}, ${Math.abs(n.gap_pct).toFixed(1)} points out, measured ${n.scope}.`;
    }
    case "deadline": {
      const n = fact.numbers;
      const cover =
        n.coverage_pct === null || n.coverage_pct === undefined
          ? ""
          : ` Liquid assets cover ${Math.round(n.coverage_pct)}% of it.`;
      return `${formatMoney(n.amount, n.currency)} falls due in ${n.days} days.${cover}`;
    }
    case "facility": {
      const n = fact.numbers;
      return `Loan-to-value is ${n.ltv_pct}% against a ${n.trigger_pct}% margin-call trigger, ${Math.abs(n.gap_pct).toFixed(1)} points of headroom.`;
    }
    case "concentration": {
      const n = fact.numbers;
      return `${n.weight_pct}% of the portfolio, ${formatMoney(n.value, currency)}.`;
    }
    case "change": {
      const n = fact.numbers;
      return `${n.instrument} moved by ${formatMoney(n.delta, n.currency)} since the last snapshot.`;
    }
    case "profile": {
      const n = fact.numbers;
      return `${n.life_stage}, resident in ${n.residence}, booked in ${n.booking_centre}.`;
    }
  }
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const BRIEF_STATE = {
  Ready: { label: "Ready", color: "success" as const },
  "Needs review": { label: "Needs review", color: "warning" as const },
  "Not prepared": { label: "Not prepared", color: "danger" as const },
};

/**
 * Readiness of a client's meeting brief (PRD 5.3). A brief only counts as ready
 * once the RM has approved or edited it; a rejected one goes back in the queue.
 */
export function briefState(
  hasPreRead: boolean,
  authorship: Authorship,
): keyof typeof BRIEF_STATE {
  if (!hasPreRead) return "Not prepared";
  if (authorship === "Approved" || authorship === "Edited") return "Ready";
  return "Needs review";
}

/**
 * The RM's booked meetings for the week, ordered by day and time. Selecting one
 * switches the whole dashboard to that client (PRD 5.3); the MVP never edits or
 * synchronizes the meetings themselves.
 */
export function CompactCalendar({
  projection,
  reviews,
  selectedClient,
}: {
  projection: MondayBriefProjection;
  reviews: Record<string, Authorship>;
  selectedClient: string;
}) {
  const styles = useStyles();
  const navigate = useNavigate();
  const meetings = projection.ranking
    .filter((client) => client.meeting)
    .sort((a, b) => {
      const day =
        DAYS.indexOf((a.meeting ?? "").slice(0, 3)) -
        DAYS.indexOf((b.meeting ?? "").slice(0, 3));
      return day || (a.meeting ?? "").localeCompare(b.meeting ?? "");
    });

  return (
    <nav className={styles.calendar} aria-label="This week's meetings">
      <Body1Strong>This week</Body1Strong>
      <Caption1>
        {meetings.length === 1
          ? "1 meeting booked"
          : `${meetings.length} meetings booked`}
      </Caption1>
      <ul className={styles.strip}>
        {meetings.map((client) => {
          const selected = client.client_id === selectedClient;
          const state =
            BRIEF_STATE[
              briefState(
                Boolean(projection.pre_reads[client.client_id]),
                reviews[client.client_id] ?? "Unreviewed",
              )
            ];
          return (
            <li key={client.client_id}>
              <button
                type="button"
                aria-current={selected ? "true" : undefined}
                className={`${styles.meeting} ${selected ? styles.meetingSelected : ""}`}
                onClick={() =>
                  navigate(`/clients/${client.client_id}/pre-read`)
                }
              >
                <Caption1 className={styles.meetingWhen}>
                  {client.meeting}
                </Caption1>
                <Body1Strong>{client.name}</Body1Strong>
                <Badge appearance="tint" color={state.color} size="small">
                  {state.label}
                </Badge>
              </button>
            </li>
          );
        })}
        {meetings.length === 0 && (
          <li className={styles.empty}>
            <Caption1>No meetings are booked this week.</Caption1>
          </li>
        )}
      </ul>
    </nav>
  );
}

export function DashboardHeader({
  preRead,
  ranked,
  facts,
  asOf,
  reviewState,
  onReviewBrief,
}: {
  preRead: ClientPreRead;
  ranked: RankedClient | undefined;
  facts: ProjectionFact[];
  asOf: string;
  reviewState: string;
  onReviewBrief: () => void;
}) {
  const styles = useStyles();
  const profile = facts.find((fact) => fact.kind === "profile");
  const health = dataHealth(facts);
  const chips = profile
    ? Object.entries(profile.numbers).filter(([key]) => key !== "name")
    : [];

  return (
    <header className={styles.header}>
      <div className={styles.headerMain}>
        <p className="eyebrow accent">
          Decision pre-read · {preRead.client_id}
        </p>
        <h1 id="client-name">{preRead.name}</h1>
        {profile && <Body1>{profile.what}</Body1>}
        <ul className={styles.chips} aria-label="Client profile">
          {chips.map(([key, value]) => (
            <li key={key}>
              <Badge appearance="outline" color="informative" size="medium">
                {key.replaceAll("_", " ")}: {formatNumber(value)}
              </Badge>
            </li>
          ))}
        </ul>
      </div>
      <div className={styles.headerSide}>
        <Body1Strong>
          {ranked?.meeting
            ? `Next meeting · ${ranked.meeting}`
            : "No meeting booked"}
        </Body1Strong>
        <Caption1>{ranked?.reason ?? "No ranked reason recorded."}</Caption1>
        <Badge appearance="filled" color={health.color}>
          Data {health.label}
        </Badge>
        <Caption1>
          Insights generated from data as of {asOf} · {preRead.language}{" "}
          reporting
        </Caption1>
        <div className={styles.headerActions}>
          <Button appearance="primary" onClick={onReviewBrief}>
            Review meeting brief
          </Button>
          <div className={`review-state is-${reviewState.toLowerCase()}`}>
            {reviewState}
          </div>
        </div>
      </div>
    </header>
  );
}

export function InsightsPanel({
  preRead,
  facts,
  authorship,
}: {
  preRead: ClientPreRead;
  facts: ProjectionFact[];
  authorship: Authorship;
}) {
  const styles = useStyles();
  // A fact counts as changed when a "what changed" line cites it, or when the
  // fact engine itself emitted it as a snapshot delta (PRD 5.4).
  const changed = new Set(
    preRead.what_changed.flatMap((item) => item.citations),
  );
  const supporting = new Map(
    preRead.rules_money
      .flatMap((item) => item.citations.map((id) => [id, item.text] as const))
      .concat(
        preRead.what_changed.flatMap((item) =>
          item.citations.map((id) => [id, item.text] as const),
        ),
      ),
  );
  const insights = facts
    .filter((fact) => fact.kind !== "profile")
    .sort((a, b) => SEVERITY[a.kind].rank - SEVERITY[b.kind].rank)
    .slice(0, 3);

  if (insights.length === 0)
    return (
      <div className={styles.panel}>
        <Body1 className={styles.empty}>
          No deterministic fact reached the insight threshold for this client.
        </Body1>
      </div>
    );

  return (
    <div className={styles.panel}>
      <Caption1>
        The three highest-severity discrepancies the fact engine produced.
      </Caption1>
      <div className={styles.cards}>
        {insights.map((fact) => {
          const severity = SEVERITY[fact.kind];
          const state =
            changed.has(fact.id) || fact.kind === "change"
              ? "Changed"
              : "Unchanged";
          // The narrator often restates the fact verbatim; only show the line
          // when it adds something the headline does not already say.
          const narrative = supporting.get(fact.id);
          const matters = narrative === fact.what ? "" : narrative;
          return (
            <article className={styles.card} key={fact.id}>
              <div className={styles.cardMeta}>
                <Badge appearance="filled" color={severity.color}>
                  {severity.label}
                </Badge>
                <Badge appearance="outline" color="informative">
                  {FACT_GROUP[fact.kind]}
                </Badge>
                <Badge appearance="tint" color="informative">
                  {state}
                </Badge>
              </div>
              <Subtitle2 as="h3">{fact.what}</Subtitle2>
              {matters && <Body1>{matters}</Body1>}
              <Caption1>Confidence: {fact.confidence}</Caption1>
              <div className={styles.action}>
                <WhyButton citations={[fact.id]} clientId={preRead.client_id} />
              </div>
            </article>
          );
        })}
      </div>
      <section className={styles.group} aria-label="Suggested question">
        <Subtitle2 as="h3">Suggested question</Subtitle2>
        <Body1>{preRead.opening.text}</Body1>
        <div className={styles.action}>
          <WhyButton
            citations={preRead.opening.citations}
            clientId={preRead.client_id}
            claim={preRead.opening.text}
            authorship={authorship}
          />
        </div>
      </section>
      <section className={styles.group} aria-label="Uncertainty">
        <Subtitle2 as="h3">What we are not sure about</Subtitle2>
        <Body1>{preRead.uncertainty.text}</Body1>
        <div className={styles.action}>
          <WhyButton
            citations={preRead.uncertainty.citations}
            clientId={preRead.client_id}
            claim={preRead.uncertainty.text}
            authorship={authorship}
          />
        </div>
      </section>
    </div>
  );
}

/**
 * PRD 5.5's two-minute client summary. Every sentence is assembled from a field
 * the projection already carries, and the Why? link carries the union of their
 * citations so the whole paragraph stays traceable.
 */
export function TwoMinuteSummary({
  preRead,
  ranked,
  facts,
  authorship,
}: {
  preRead: ClientPreRead;
  ranked: RankedClient | undefined;
  facts: ProjectionFact[];
  authorship: Authorship;
}) {
  const styles = useStyles();
  const profile = facts.find(factOfKind("profile"));
  const deadline = facts.find(factOfKind("deadline"));
  const sentences: { text: string; citations: string[] }[] = [];

  if (profile)
    sentences.push({
      text: `${profile.what} ${stake(profile)} Reporting runs in ${profile.numbers.currency} and ${profile.numbers.language}.`,
      citations: [profile.id],
    });
  // The ranking reason is often the gap verbatim; only add it when it says
  // something the "data says" sentence below does not.
  const reason =
    ranked?.reason && ranked.reason !== preRead.gap.data
      ? ` ${ranked.reason}`
      : "";
  sentences.push({
    text: ranked?.meeting
      ? `You meet ${preRead.name} on ${ranked.meeting}.${reason}`
      : `No meeting is booked with ${preRead.name} this week.${reason}`,
    citations: ranked?.citations ?? [],
  });
  sentences.push({
    text: `The client told us “${preRead.gap.belief}” The data says ${preRead.gap.data}`,
    citations: preRead.gap.citations,
  });
  if (deadline)
    sentences.push({ text: stake(deadline), citations: [deadline.id] });
  if (preRead.what_changed.length > 0)
    sentences.push({
      text: `${preRead.what_changed.length} position${preRead.what_changed.length === 1 ? "" : "s"} moved since the last snapshot.`,
      citations: preRead.what_changed.flatMap((item) => item.citations),
    });

  return (
    <>
      <Body1 as="p" className={styles.summary}>
        {sentences.map((sentence) => sentence.text).join(" ")}
      </Body1>
      <div className={styles.headerActions}>
        <WhyButton
          citations={[
            ...new Set(sentences.flatMap((sentence) => sentence.citations)),
          ]}
          clientId={preRead.client_id}
          claim={sentences.map((sentence) => sentence.text).join(" ")}
          authorship={authorship}
        />
      </div>
    </>
  );
}

/**
 * PRD 5.5's three discussion topics: the agenda, severity-ranked, each with the
 * quantified stake pulled from the fact's own calculation inputs.
 */
export function DiscussionTopics({
  facts,
  clientId,
}: {
  facts: ProjectionFact[];
  clientId: string;
}) {
  const styles = useStyles();
  const currency = facts.find(factOfKind("profile"))?.numbers.currency;
  const topics = facts
    .filter((fact) => fact.kind !== "profile")
    .sort((a, b) => SEVERITY[a.kind].rank - SEVERITY[b.kind].rank)
    .slice(0, 3);

  if (topics.length === 0)
    return (
      <Body1 className={styles.empty}>
        No deterministic fact reached the agenda threshold for this client.
      </Body1>
    );

  return (
    <ol className={styles.topics}>
      {topics.map((fact, index) => (
        <li className={styles.topic} key={fact.id}>
          <div className={styles.cardMeta}>
            <Badge appearance="filled" color={SEVERITY[fact.kind].color}>
              Topic {index + 1}
            </Badge>
            <Badge appearance="outline" color="informative">
              {FACT_GROUP[fact.kind]}
            </Badge>
          </div>
          <Subtitle2 as="h3">{fact.what}</Subtitle2>
          <Body1 as="p" className={styles.summary}>
            {stake(fact, currency)}
          </Body1>
          <div className={styles.headerActions}>
            <WhyButton citations={[fact.id]} clientId={clientId} />
          </div>
        </li>
      ))}
    </ol>
  );
}

/**
 * PRD 5.5's open commitments: the planned cash needs the client's own facts
 * cite, so the RM sees what money is already spoken for before advising.
 */
export function OpenCommitments({
  facts,
  evidence,
  clientId,
}: {
  facts: ProjectionFact[];
  evidence: MondayBriefProjection["evidence"];
  clientId: string;
}) {
  const styles = useStyles();
  const commitments = [...new Set(facts.flatMap((fact) => fact.source_rows))]
    .filter((row) => row.startsWith("planned_cash_needs:"))
    .map((row) => evidence[row])
    .filter(Boolean)
    .sort((a, b) =>
      String(a.record.due_from).localeCompare(String(b.record.due_from)),
    );

  if (commitments.length === 0)
    return (
      <Body1 className={styles.empty}>
        No planned cash need is recorded against this client.
      </Body1>
    );

  return (
    <div className={styles.cards}>
      {commitments.map((commitment) => {
        const record = commitment.record;
        const amount =
          typeof record.amount === "number"
            ? formatMoney(record.amount, String(record.currency ?? ""))
            : "Amount not recorded";
        return (
          <article className={styles.card} key={commitment.id}>
            <Body1Strong>
              {String(record.description ?? commitment.title)}
            </Body1Strong>
            <Subtitle2 as="p">{amount}</Subtitle2>
            <Caption1>
              Due {String(record.due_from)} to {String(record.due_to)} ·{" "}
              {String(record.certainty ?? "Certainty not recorded")}
            </Caption1>
            <div className={styles.action}>
              <WhyButton citations={[commitment.id]} clientId={clientId} />
            </div>
          </article>
        );
      })}
    </div>
  );
}

export function DataPanel({
  facts,
  clientId,
}: {
  facts: ProjectionFact[];
  clientId: string;
}) {
  const styles = useStyles();
  const kinds = [...new Set(facts.map((fact) => fact.kind))];

  return (
    <div className={styles.panel}>
      <Caption1>
        Every deterministic fact behind this client, with the calculation inputs
        and a link to its exact source rows.
      </Caption1>
      {kinds.map((kind) => (
        <section
          className={styles.group}
          key={kind}
          aria-label={FACT_GROUP[kind]}
        >
          <Subtitle2 as="h3">{FACT_GROUP[kind]}</Subtitle2>
          <div className={styles.cards}>
            {facts
              .filter((fact) => fact.kind === kind)
              .map((fact) => (
                <article className={styles.card} key={fact.id}>
                  <Body1Strong>{fact.what}</Body1Strong>
                  <FactNumbers fact={fact} />
                  <Caption1>
                    Confidence: {fact.confidence} · {fact.source_rows.length}{" "}
                    source row{fact.source_rows.length === 1 ? "" : "s"}
                  </Caption1>
                  <div className={styles.action}>
                    <WhyButton citations={[fact.id]} clientId={clientId} />
                  </div>
                </article>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}

export function MemoryPanel({
  preRead,
  evidence,
}: {
  preRead: ClientPreRead;
  evidence: MondayBriefProjection["evidence"];
}) {
  const styles = useStyles();
  const notes = Object.values(evidence)
    .filter(
      (item) =>
        item.kind === "RM note" && item.record.client_id === preRead.client_id,
    )
    .sort((a, b) =>
      String(a.record.note_date).localeCompare(String(b.record.note_date)),
    );

  return (
    <div className={styles.panel}>
      <section className={styles.group} aria-label="Extracted beliefs">
        <Subtitle2 as="h3">What the client told us</Subtitle2>
        <div className={styles.cards}>
          {preRead.beliefs.map((belief) => (
            <article className={styles.card} key={belief.id}>
              <Body1>“{belief.text}”</Body1>
              <Caption1>Note {belief.note_id}</Caption1>
              <div className={styles.action}>
                <WhyButton
                  citations={belief.citations}
                  clientId={preRead.client_id}
                />
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className={styles.group} aria-label="RM notes">
        <Subtitle2 as="h3">RM notes</Subtitle2>
        {notes.length === 0 ? (
          <Body1 className={styles.empty}>
            No RM note is recorded for this client.
          </Body1>
        ) : (
          notes.map((note) => (
            <div className={styles.note} key={note.id}>
              <Caption1>
                {String(note.record.note_date)} ·{" "}
                {String(note.record.channel ?? "Note")} ·{" "}
                {String(note.record.rm_name ?? "RM")}
              </Caption1>
              <Body1>{String(note.record.note ?? note.title)}</Body1>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
