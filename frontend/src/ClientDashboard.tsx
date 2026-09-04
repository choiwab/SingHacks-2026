import {
  Badge,
  Body1,
  Button,
  Body1Strong,
  Caption1,
  SearchBox,
  Subtitle2,
  makeStyles,
  mergeClasses,
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
import { useEffect, useRef } from "react";

import { AUTHORSHIP } from "./evidence";
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
  topInsights: {
    // Separates the always-visible insight strip from the tabs beneath it.
    paddingBlockEnd: tokens.spacingVerticalXXL,
    borderBottomWidth: "2px",
    borderBottomStyle: "solid",
    borderBottomColor: tokens.colorNeutralStroke2,
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
  measure: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
  },
  track: {
    position: "relative",
    blockSize: "0.5rem",
    ...shorthands.borderRadius(tokens.borderRadiusSmall),
    backgroundColor: tokens.colorNeutralBackground4,
    // The limit marker sits at limit/scale, which is always inside the track.
    overflow: "hidden",
  },
  fill: {
    blockSize: "100%",
    ...shorthands.borderRadius(tokens.borderRadiusSmall),
    backgroundColor: tokens.colorPaletteGreenBackground3,
  },
  fillBreached: {
    backgroundColor: tokens.colorPaletteRedBackground3,
  },
  fillPlain: {
    backgroundColor: tokens.colorBrandBackground,
  },
  limitMark: {
    position: "absolute",
    insetBlockStart: 0,
    insetBlockEnd: 0,
    inlineSize: "2px",
    backgroundColor: tokens.colorNeutralForeground1,
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
  // Cards in a row stretch to the tallest; pushing the action down keeps the
  // three "Why?" links on one baseline instead of following ragged copy.
  cardAction: {
    alignSelf: "flex-start",
    marginBlockStart: "auto",
  },
  empty: {
    color: tokens.colorNeutralForeground3,
  },
  search: {
    maxWidth: "26rem",
    width: "100%",
  },
  memory: {
    overflowWrap: "anywhere",
  },
  mark: {
    backgroundColor: tokens.colorBrandBackground2,
    color: tokens.colorBrandForeground2,
    ...shorthands.borderRadius(tokens.borderRadiusSmall),
    ...shorthands.padding(0, "0.1em"),
    fontWeight: tokens.fontWeightSemibold,
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

function mandateBreached(fact: FactOf<"mandate_gap">) {
  const n = fact.numbers;
  return n.boundary === "minimum"
    ? n.actual_pct < n.limit_pct
    : n.actual_pct > n.limit_pct;
}

function insightSeverity(fact: ProjectionFact) {
  if (fact.kind === "mandate_gap" && !mandateBreached(fact)) {
    return { rank: 5, label: "Within limit", color: "informative" as const };
  }
  return SEVERITY[fact.kind];
}

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
      if (!mandateBreached(fact))
        return `Within the ${n.limit_pct}% ${n.boundary}, measured ${n.scope}.`;
      // The headline already states the actual and the limit; the stake adds
      // how far out it is and what the measurement covers.
      return `${Math.abs(n.gap_pct).toFixed(1)} points outside the ${n.limit_pct}% ${n.boundary}, measured ${n.scope}.`;
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

/**
 * A fact whose calculation inputs put a measured value on a scale, so the card
 * can show how far outside it sits instead of only stating the two numbers.
 * `limit` is the threshold the fact engine emitted; a fact with no threshold in
 * its inputs gets a plain proportion bar rather than an invented line.
 *
 * Deadline and change facts get no bar: their inputs are money and days, not a
 * position on one scale.
 */
type Measure = {
  label: string;
  actual: number;
  scale: number;
  limit?: number;
  breached: boolean;
};

export function measure(fact: ProjectionFact): Measure | undefined {
  switch (fact.kind) {
    case "mandate_gap": {
      const n = fact.numbers;
      // Headroom past the larger of the two keeps the marker off the end. Some
      // clients carry a degenerate 0% against 0% band, which draws nothing.
      const scale = Math.max(n.actual_pct, n.limit_pct) * 1.1;
      if (scale <= 0) return undefined;
      return {
        label: `${n.asset_class} allocation against the ${n.limit_pct}% ${n.boundary}`,
        actual: n.actual_pct,
        limit: n.limit_pct,
        scale,
        breached: mandateBreached(fact),
      };
    }
    case "facility": {
      const n = fact.numbers;
      const scale = Math.max(n.ltv_pct, n.trigger_pct) * 1.1;
      if (scale <= 0) return undefined;
      return {
        label: `Loan-to-value against the ${n.trigger_pct}% margin-call trigger`,
        actual: n.ltv_pct,
        limit: n.trigger_pct,
        scale,
        breached: n.ltv_pct > n.trigger_pct,
      };
    }
    case "concentration":
      // No threshold exists for concentration, so this is a plain proportion
      // of the portfolio with no line to cross.
      return {
        label: "Connected positions as a share of the portfolio",
        actual: fact.numbers.weight_pct,
        scale: 100,
        breached: false,
      };
    default:
      return undefined;
  }
}

/**
 * The one visual on an insight card (PRD 5.4, 5.6): where the measured value
 * sits against the mandate or trigger line the fact engine supplied. The track
 * is aria-hidden because the caption and the fact headline already state every
 * number it draws.
 */
function MeasureBar({ fact }: { fact: ProjectionFact }) {
  const styles = useStyles();
  const bar = measure(fact);
  if (!bar) return null;

  const percent = (value: number) =>
    `${Math.min(100, (value / bar.scale) * 100)}%`;

  return (
    <div className={styles.measure}>
      <Caption1>{bar.label}</Caption1>
      <div className={styles.track} aria-hidden="true">
        <div
          className={mergeClasses(
            styles.fill,
            bar.breached && styles.fillBreached,
            bar.limit === undefined && styles.fillPlain,
          )}
          style={{ inlineSize: percent(bar.actual) }}
        />
        {bar.limit === undefined ? null : (
          <div
            className={styles.limitMark}
            style={{ insetInlineStart: percent(bar.limit) }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * The question this fact puts to the client (PRD 5.4, 5.5). The narrator emits
 * one opening question for the whole brief, so a per-insight prompt is derived
 * from the same calculation inputs the card already displays - it asks for the
 * client's intent, which is the one thing no deterministic tool can supply.
 */
function askAbout(fact: ProjectionFact): string {
  switch (fact.kind) {
    case "mandate_gap": {
      const n = fact.numbers;
      if (!mandateBreached(fact))
        return `Does the ${n.limit_pct}% ${n.boundary} for ${n.asset_class} still fit your objectives?`;
      return `Do you want ${n.asset_class} brought back inside the ${n.limit_pct}% ${n.boundary}, or should we revisit the mandate itself?`;
    }
    case "deadline": {
      const n = fact.numbers;
      return `Which holdings should we raise the ${formatMoney(n.amount, n.currency)} from, and when do you need it settled?`;
    }
    case "facility": {
      const n = fact.numbers;
      return `How much headroom do you want above the ${n.trigger_pct}% margin-call trigger if markets fall further?`;
    }
    case "concentration": {
      const n = fact.numbers;
      return `Are you comfortable with ${n.weight_pct}% of the portfolio sitting in connected positions?`;
    }
    case "change": {
      const n = fact.numbers;
      return `Was the ${formatMoney(Math.abs(n.delta), n.currency)} move in ${n.instrument} intentional?`;
    }
    case "profile": {
      const n = fact.numbers;
      return `Has anything changed about ${n.life_stage.toLowerCase()} since we last spoke?`;
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
  onOpenSelectedBrief,
}: {
  projection: MondayBriefProjection;
  reviews: Record<string, Authorship>;
  selectedClient: string;
  onOpenSelectedBrief?: () => void;
}) {
  const styles = useStyles();
  const navigate = useNavigate();
  const selectedMeeting = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const button = selectedMeeting.current;
    const strip = button?.closest("ul");
    if (!button || !strip) return;
    const meetingBounds = button.getBoundingClientRect();
    const stripBounds = strip.getBoundingClientRect();
    // Reveal the meeting horizontally without scrolling the dashboard or
    // moving focus away from the navigation destination.
    if (meetingBounds.left < stripBounds.left) {
      strip.scrollLeft += meetingBounds.left - stripBounds.left;
    } else if (meetingBounds.right > stripBounds.right) {
      strip.scrollLeft += meetingBounds.right - stripBounds.right;
    }
  }, [selectedClient]);

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
                ref={selected ? selectedMeeting : undefined}
                aria-current={selected ? "true" : undefined}
                className={`${styles.meeting} ${selected ? styles.meetingSelected : ""}`}
                onClick={() => {
                  if (selected && onOpenSelectedBrief) {
                    onOpenSelectedBrief();
                  } else {
                    navigate(`/clients/${client.client_id}/pre-read`);
                  }
                }}
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
            <Caption1>No meetings booked this week.</Caption1>
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
  reviewState: Authorship;
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
        {profile && (
          <div className={styles.action}>
            <WhyButton citations={[profile.id]} clientId={preRead.client_id}>
              Why this profile?
            </WhyButton>
          </div>
        )}
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
          Data as of {asOf} · reporting in {preRead.language}
        </Caption1>
        <div className={styles.headerActions}>
          <Button appearance="primary" onClick={onReviewBrief}>
            Review meeting brief
          </Button>
          <Badge appearance="tint" color={AUTHORSHIP[reviewState].color}>
            {AUTHORSHIP[reviewState].label}
          </Badge>
        </div>
      </div>
    </header>
  );
}

/**
 * Ranked insight candidates: every non-profile fact, highest severity first.
 * The dashboard shows the leading three (PRD 5.4); the Insights tab shows the
 * rest, so a lower-severity fact is still reachable without competing for
 * attention on the first screen.
 */
function rankedInsights(facts: ProjectionFact[]) {
  return facts
    .filter((fact) => fact.kind !== "profile")
    .sort((a, b) => insightSeverity(a).rank - insightSeverity(b).rank);
}

/**
 * The narrator's line for a fact, when it says something the headline does not
 * already say. Otherwise the quantified stake, so "why it matters" is never
 * blank on a card.
 */
function whyItMatters(
  fact: ProjectionFact,
  supporting: Map<string, string>,
  currency: string | undefined,
) {
  const narrative = supporting.get(fact.id);
  return narrative && narrative !== fact.what
    ? narrative
    : stake(fact, currency);
}

function InsightCard({
  fact,
  clientId,
  clientName,
  authorship,
  state,
  matters,
  uncertainty,
}: {
  fact: ProjectionFact;
  clientId: string;
  clientName: string;
  authorship: Authorship;
  state: "Changed" | "Unchanged";
  matters: string;
  uncertainty?: string;
}) {
  const styles = useStyles();
  const severity = insightSeverity(fact);
  const question = askAbout(fact);
  const claim = [
    `${clientName} · ${FACT_GROUP[fact.kind]} · ${state} · ${fact.what}`,
    matters,
    `Ask: ${question}`,
    uncertainty ? `To confirm: ${uncertainty}` : undefined,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <article className={styles.card}>
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
      <MeasureBar fact={fact} />
      <Body1 as="p" className={styles.summary}>
        {matters}
      </Body1>
      <div className={styles.note}>
        <Caption1 className={styles.term}>Ask</Caption1>
        <Body1 as="p" className={styles.summary}>
          {question}
        </Body1>
      </div>
      <Caption1>Confidence: {fact.confidence}</Caption1>
      {uncertainty ? <Caption1>To confirm: {uncertainty}</Caption1> : null}
      <div className={styles.cardAction}>
        <WhyButton
          citations={[fact.id]}
          clientId={clientId}
          claim={claim}
          authorship={authorship}
        />
      </div>
    </article>
  );
}

/**
 * Reads which facts the brief describes as having moved. A fact counts as
 * changed when a "what changed" line cites it, or when the fact engine itself
 * emitted it as a snapshot delta (PRD 5.4).
 */
function useInsightContext(preRead: ClientPreRead, facts: ProjectionFact[]) {
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
  const currency = facts.find(factOfKind("profile"))?.numbers.currency;
  const state = (fact: ProjectionFact) =>
    changed.has(fact.id) || fact.kind === "change"
      ? ("Changed" as const)
      : ("Unchanged" as const);
  const matters = (fact: ProjectionFact) =>
    whyItMatters(fact, supporting, currency);
  // PRD 5.4 wants uncertainty on the card, and the brief's single uncertainty
  // names the facts it applies to, so it is only shown on those.
  const uncertainty = (fact: ProjectionFact) =>
    preRead.uncertainty.citations.includes(fact.id)
      ? preRead.uncertainty.text
      : undefined;
  return { state, matters, uncertainty };
}

/**
 * PRD 5.4's top insights. They sit above the tabs rather than inside one, so
 * the client summary, the discrepancies and the brief action are all visible
 * from a single interaction.
 */
export function TopInsights({
  preRead,
  facts,
  authorship,
}: {
  preRead: ClientPreRead;
  facts: ProjectionFact[];
  authorship: Authorship;
}) {
  const styles = useStyles();
  const { state, matters, uncertainty } = useInsightContext(preRead, facts);
  const insights = rankedInsights(facts).slice(0, 3);

  return (
    <section
      className={mergeClasses(styles.panel, styles.topInsights)}
      aria-labelledby="top-insights-title"
    >
      <div className={styles.group}>
        <Subtitle2 as="h2" id="top-insights-title">
          Top insights
        </Subtitle2>
        <Caption1>Highest severity first.</Caption1>
      </div>
      {insights.length === 0 ? (
        <Body1 className={styles.empty}>No insights for this client.</Body1>
      ) : (
        <div className={styles.cards}>
          {insights.map((fact) => (
            <InsightCard
              key={fact.id}
              fact={fact}
              clientId={preRead.client_id}
              clientName={preRead.name}
              authorship={authorship}
              state={state(fact)}
              matters={matters(fact)}
              uncertainty={uncertainty(fact)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * The Insights tab (PRD 5.6): the insights the top three pushed below the fold,
 * plus the suggested question and the single uncertainty that apply to all of
 * them.
 */
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
  const { state, matters, uncertainty } = useInsightContext(preRead, facts);
  const rest = rankedInsights(facts).slice(3);

  return (
    <div className={styles.panel}>
      <section className={styles.group} aria-labelledby="also-active-title">
        <Subtitle2 as="h3" id="also-active-title">
          Also active
        </Subtitle2>
        <Caption1>Lower-severity facts, below the top three.</Caption1>
        {rest.length === 0 ? (
          <Body1 className={styles.empty}>
            Every insight for this client is shown above.
          </Body1>
        ) : (
          <div className={styles.cards}>
            {rest.map((fact) => (
              <InsightCard
                key={fact.id}
                fact={fact}
                clientId={preRead.client_id}
                clientName={preRead.name}
                authorship={authorship}
                state={state(fact)}
                matters={matters(fact)}
                uncertainty={uncertainty(fact)}
              />
            ))}
          </div>
        )}
      </section>
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
      ? `The meeting is ${ranked.meeting}.${reason}`
      : `No meeting is booked this week.${reason}`,
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
  clientName,
  authorship,
}: {
  facts: ProjectionFact[];
  clientId: string;
  clientName: string;
  authorship: Authorship;
}) {
  const styles = useStyles();
  const currency = facts.find(factOfKind("profile"))?.numbers.currency;
  const topics = rankedInsights(facts).slice(0, 3);

  if (topics.length === 0)
    return (
      <Body1 className={styles.empty}>No agenda topics for this client.</Body1>
    );

  return (
    <ol className={styles.topics}>
      {topics.map((fact, index) => {
        const summary = stake(fact, currency);
        const question = askAbout(fact);
        return (
          <li className={styles.topic} key={fact.id}>
            <div className={styles.cardMeta}>
              <Badge appearance="filled" color={insightSeverity(fact).color}>
                Topic {index + 1}
              </Badge>
              <Badge appearance="outline" color="informative">
                {FACT_GROUP[fact.kind]}
              </Badge>
            </div>
            <Subtitle2 as="h3">{fact.what}</Subtitle2>
            <Body1 as="p" className={styles.summary}>
              {summary}
            </Body1>
            <div className={styles.note}>
              <Caption1 className={styles.term}>Ask</Caption1>
              <Body1 as="p" className={styles.summary}>
                {question}
              </Body1>
            </div>
            <div className={styles.headerActions}>
              <WhyButton
                citations={[fact.id]}
                clientId={clientId}
                claim={`${clientName} · Topic ${index + 1} · ${fact.what} ${summary} Ask: ${question}`}
                authorship={authorship}
              />
            </div>
          </li>
        );
      })}
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
  clientName,
}: {
  facts: ProjectionFact[];
  evidence: MondayBriefProjection["evidence"];
  clientId: string;
  clientName: string;
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
      <Body1 className={styles.empty}>No planned cash needs recorded.</Body1>
    );

  return (
    <div className={styles.cards}>
      {commitments.map((commitment) => {
        const record = commitment.record;
        const amount =
          typeof record.amount === "number"
            ? formatMoney(record.amount, String(record.currency ?? ""))
            : "Amount not recorded";
        const description = String(record.description ?? commitment.title);
        const timing = `Due ${String(record.due_from)} to ${String(record.due_to)} · ${String(record.certainty ?? "Certainty not recorded")}`;
        return (
          <article className={styles.card} key={commitment.id}>
            <Body1Strong>{description}</Body1Strong>
            <Subtitle2 as="p">{amount}</Subtitle2>
            <Caption1>{timing}</Caption1>
            <div className={styles.action}>
              <WhyButton
                citations={[commitment.id]}
                clientId={clientId}
                claim={`${clientName} · ${description} · ${amount} · ${timing}`}
              />
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
  clientName,
}: {
  facts: ProjectionFact[];
  clientId: string;
  clientName: string;
}) {
  const styles = useStyles();
  const kinds = [...new Set(facts.map((fact) => fact.kind))];

  return (
    <div className={styles.panel}>
      <Caption1>
        Every fact behind this client, with its calculation inputs and source
        rows.
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
                  <MeasureBar fact={fact} />
                  <FactNumbers fact={fact} />
                  <Caption1>
                    Confidence: {fact.confidence} · {fact.source_rows.length}{" "}
                    source row{fact.source_rows.length === 1 ? "" : "s"}
                  </Caption1>
                  <div className={styles.action}>
                    <WhyButton
                      citations={[fact.id]}
                      clientId={clientId}
                      claim={`${clientName} · ${fact.what}`}
                    />
                  </div>
                </article>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/**
 * Question words and glue the RM will type but that carry no signal, so
 * "What did she say about risk?" retrieves on "risk" alone.
 */
const STOPWORDS = new Set(
  `a about all an and any are as ask at be been but by can did do does for from
   get had has have he her him his how i if in into is it its me my not of on or
   our say said she that the their them then there these they this to told
   under up us was we were what when where which who whom why will with would
   you your`.split(/\s+/),
);

/**
 * PRD 4 nice-to-have: retrieval over the selected client's RM notes. Distinct
 * term overlap against one client's note set, which is tens of short records.
 * ponytail: keyword scoring, swap for a pipeline retriever if one ever lands.
 */
function queryTerms(query: string): string[] {
  return [
    ...new Set(
      query
        .split(/[^\p{L}\p{N}]+/u)
        .filter(
          (word) =>
            word.length > 1 &&
            // Preserve the region abbreviation, but still ignore conversational "us".
            (word === "US" || !STOPWORDS.has(word.toLowerCase())),
        )
        .map((word) => word.toLowerCase()),
    ),
  ];
}

/** How many distinct query terms the text contains. */
function matchScore(text: string, terms: string[]): number {
  return terms.filter((term) => new RegExp(termPattern(term), "iu").test(text))
    .length;
}

/** Short terms such as UK, Q2 and FX must not match inside unrelated words. */
function termPattern(term: string): string {
  return term.length === 2
    ? `(?<![\\p{L}\\p{N}])${term}(?![\\p{L}\\p{N}])`
    : term;
}

/**
 * Keeps the retrieved records readable by marking the words that matched.
 * Terms are letters and digits only by construction, so they need no escaping
 * before going into the split pattern.
 */
function Highlight({ text, terms }: { text: string; terms: string[] }) {
  const styles = useStyles();
  if (terms.length === 0) return <>{text}</>;
  const parts = text.split(
    new RegExp(`(${terms.map(termPattern).join("|")})`, "giu"),
  );
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 1 ? (
          <mark className={styles.mark} key={index}>
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </>
  );
}

const plural = (count: number, word: string) =>
  `${count} ${word}${count === 1 ? "" : "s"}`;

/** Best match first; equal scores keep the order they were given in. */
function retrieve<T>(items: T[], terms: string[], text: (item: T) => string) {
  if (terms.length === 0) return items;
  return items
    .map((item) => ({ item, score: matchScore(text(item), terms) }))
    .filter((hit) => hit.score > 0)
    .sort((a, b) => b.score - a.score)
    .map((hit) => hit.item);
}

export function MemoryPanel({
  preRead,
  evidence,
  query,
  onQueryChange,
}: {
  preRead: ClientPreRead;
  evidence: MondayBriefProjection["evidence"];
  query: string;
  onQueryChange: (query: string) => void;
}) {
  const styles = useStyles();
  const terms = queryTerms(query);
  const notes = Object.values(evidence)
    .filter(
      (item) =>
        item.kind === "RM note" && item.record.client_id === preRead.client_id,
    )
    .sort((a, b) =>
      String(a.record.note_date).localeCompare(String(b.record.note_date)),
    );
  const noteText = (note: (typeof notes)[number]) =>
    `${String(note.record.note ?? note.title)} ${String(note.record.channel ?? "")}`;

  const matchedNotes = retrieve(notes, terms, noteText);
  const matchedBeliefs = retrieve(
    preRead.beliefs,
    terms,
    (belief) => belief.text,
  );

  return (
    <div className={mergeClasses(styles.panel, styles.memory)}>
      <section className={styles.group} aria-label="Search the client memory">
        <Subtitle2 as="h3">Ask the notes</Subtitle2>
        <SearchBox
          className={styles.search}
          placeholder="What did they say about risk?"
          aria-label="Search this client's RM notes"
          dismiss={{ "aria-label": "Clear note search" }}
          value={query}
          onChange={(_, data) => onQueryChange(data.value)}
        />
        <Caption1 role="status">
          {terms.length === 0 &&
            query.trim() &&
            "Add a topic such as risk, tax, or cash to search. "}
          {terms.length === 0
            ? `${query.trim() ? "Showing all" : "Searching"} ${plural(notes.length, "note")} and ${plural(preRead.beliefs.length, "extracted belief")} for this client.`
            : `${matchedNotes.length} of ${plural(notes.length, "note")} and ${matchedBeliefs.length} of ${plural(preRead.beliefs.length, "belief")} mention ${terms.join(" or ")}.`}
        </Caption1>
      </section>
      <section className={styles.group} aria-label="Extracted beliefs">
        <Subtitle2 as="h3">What the client told us</Subtitle2>
        {matchedBeliefs.length === 0 ? (
          <Body1 className={styles.empty}>
            {preRead.beliefs.length === 0
              ? "No extracted beliefs available."
              : `No recorded belief mentions ${terms.join(" or ")}.`}
          </Body1>
        ) : (
          <div className={styles.cards}>
            {matchedBeliefs.map((belief) => (
              <article className={styles.card} key={belief.id}>
                <Body1>
                  “<Highlight text={belief.text} terms={terms} />”
                </Body1>
                <Caption1>Note {belief.note_id}</Caption1>
                <div className={styles.action}>
                  <WhyButton
                    citations={belief.citations}
                    clientId={preRead.client_id}
                    claim={`${preRead.name} · Extracted belief: “${belief.text}”`}
                  />
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <section className={styles.group} aria-label="RM notes">
        <Subtitle2 as="h3">
          {terms.length === 0 ? "RM notes" : "Matching RM notes"}
        </Subtitle2>
        {matchedNotes.length === 0 ? (
          <Body1 className={styles.empty}>
            {notes.length === 0
              ? "No RM notes recorded."
              : `No note mentions ${terms.join(" or ")}. Try another word.`}
          </Body1>
        ) : (
          matchedNotes.map((note) => (
            <div className={styles.note} key={note.id}>
              <Caption1>
                {String(note.record.note_date)} ·{" "}
                <Highlight
                  text={String(note.record.channel ?? "Note")}
                  terms={terms}
                />{" "}
                · {String(note.record.rm_name ?? "RM")}
              </Caption1>
              <Body1>
                <Highlight
                  text={String(note.record.note ?? note.title)}
                  terms={terms}
                />
              </Body1>
              <div className={styles.action}>
                <WhyButton citations={[note.id]} clientId={preRead.client_id} />
              </div>
            </div>
          ))
        )}
      </section>
    </div>
  );
}
