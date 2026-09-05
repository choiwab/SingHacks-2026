import {
  Badge,
  Card,
  Title1,
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

const FACT_GROUP: Record<ProjectionFact["kind"], string> = {
  profile: "Profile",
  mandate_gap: "Mandate",
  deadline: "Cash need",
  facility: "Collateral",
  concentration: "Concentration",
  change: "Snapshot change",
};

import { NARROW, formatValue } from "./presentation";

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
  factPreview: {
    // Separates the always-visible insight strip from the tabs beneath it.
    paddingBlockEnd: tokens.spacingVerticalXXL,
    borderBottomWidth: "2px",
    borderBottomStyle: "solid",
    borderBottomColor: tokens.colorNeutralStroke2,
  },
  cards: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(17rem, 100%), 1fr))",
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
});

function FactNumbers({ fact }: { fact: ProjectionFact }) {
  const styles = useStyles();
  return (
    <dl className={styles.numbers}>
      {Object.entries(fact.numbers).map(([key, value]) => (
        <div key={key} style={{ display: "contents" }}>
          <dt className={styles.term}>{key.replaceAll("_", " ")}</dt>
          <dd className={styles.value}>{formatValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

type FactOf<K extends ProjectionFact["kind"]> = Extract<
  ProjectionFact,
  { kind: K }
>;

function mandateBreached(fact: FactOf<"mandate_gap">) {
  const n = fact.numbers;
  return n.boundary === "minimum"
    ? n.actual_pct < n.limit_pct
    : n.actual_pct > n.limit_pct;
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
  const chips = profile
    ? Object.entries(profile.numbers).filter(([key]) => key !== "name")
    : [];

  return (
    <header className={styles.header}>
      <div className={styles.headerMain}>
        <Caption1>Meeting brief · {preRead.client_id}</Caption1>
        <Title1 as="h1" id="client-name">
          {preRead.name}
        </Title1>
        {profile && <Body1>{profile.what}</Body1>}
        <ul className={styles.chips} aria-label="Client profile">
          {chips.map(([key, value]) => (
            <li key={key}>
              <Badge appearance="outline" color="informative" size="medium">
                {key.replaceAll("_", " ")}: {formatValue(value)}
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
        <Caption1>Meeting purpose not recorded.</Caption1>
        <Badge appearance="outline" color="informative">
          Data health unavailable
        </Badge>
        <Caption1>Refresh and insight times unavailable.</Caption1>
        <Caption1>Data as of {asOf}</Caption1>
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

/** Facts retain the order supplied by the projection until ranked insights exist. */
function displayedFacts(facts: ProjectionFact[]) {
  return facts.filter((fact) => fact.kind !== "profile");
}

function FactCard({
  fact,
  clientId,
  clientName,
  authorship,
  uncertainty,
}: {
  fact: ProjectionFact;
  clientId: string;
  clientName: string;
  authorship: Authorship;
  uncertainty?: string;
}) {
  const styles = useStyles();
  const claim = [
    `${clientName} · ${FACT_GROUP[fact.kind]} · ${fact.what}`,
    uncertainty ? `To confirm: ${uncertainty}` : undefined,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Card role="article" className={styles.card}>
      <div className={styles.cardMeta}>
        <Badge appearance="outline" color="informative">
          {FACT_GROUP[fact.kind]}
        </Badge>
      </div>
      <Subtitle2 as="h3">{fact.what}</Subtitle2>
      <MeasureBar fact={fact} />
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
    </Card>
  );
}

/**
 * Show the first three facts without claiming a priority the projection lacks.
 */
export function FactPreview({
  preRead,
  facts,
  authorship,
}: {
  preRead: ClientPreRead;
  facts: ProjectionFact[];
  authorship: Authorship;
}) {
  const styles = useStyles();
  const preview = displayedFacts(facts).slice(0, 3);

  return (
    <section
      className={mergeClasses(styles.panel, styles.factPreview)}
      aria-labelledby="client-facts-title"
    >
      <div className={styles.group}>
        <Subtitle2 as="h2" id="client-facts-title">
          Client facts
        </Subtitle2>
        <Caption1>
          Facts in source order. Ranked insights and update status unavailable.
        </Caption1>
      </div>
      {preview.length === 0 ? (
        <Body1 className={styles.empty}>No facts for this client.</Body1>
      ) : (
        <div className={styles.cards}>
          {preview.map((fact) => (
            <FactCard
              key={fact.id}
              fact={fact}
              clientId={preRead.client_id}
              clientName={preRead.name}
              authorship={authorship}
              uncertainty={
                preRead.uncertainty.citations.includes(fact.id)
                  ? preRead.uncertainty.text
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * Remaining facts and the supplied opening and uncertainty.
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
  const rest = displayedFacts(facts).slice(3);

  return (
    <div className={styles.panel}>
      <section className={styles.group} aria-labelledby="also-active-title">
        <Subtitle2 as="h3" id="also-active-title">
          More client facts
        </Subtitle2>
        {rest.length === 0 ? (
          <Body1 className={styles.empty}>
            All client facts are shown above.
          </Body1>
        ) : (
          <div className={styles.cards}>
            {rest.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                clientId={preRead.client_id}
                clientName={preRead.name}
                authorship={authorship}
                uncertainty={
                  preRead.uncertainty.citations.includes(fact.id)
                    ? preRead.uncertainty.text
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </section>
      <section className={styles.group} aria-label="Suggested opening">
        <Subtitle2 as="h3">Suggested opening</Subtitle2>
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
        <Subtitle2 as="h3">Uncertainty</Subtitle2>
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

/** Planned cash-need facts as supplied; source details remain in the evidence drawer. */
export function PlannedCashNeeds({
  facts,
  clientId,
  clientName,
}: {
  facts: ProjectionFact[];
  clientId: string;
  clientName: string;
}) {
  const styles = useStyles();
  const needs = facts.filter((fact) => fact.kind === "deadline");
  if (needs.length === 0)
    return <Body1>No planned cash needs included in this brief.</Body1>;
  return (
    <div className={styles.cards}>
      {needs.map((fact) => (
        <Card role="article" key={fact.id}>
          <Body1Strong>{fact.what}</Body1Strong>
          <FactNumbers fact={fact} />
          <div className={styles.action}>
            <WhyButton
              citations={[fact.id]}
              clientId={clientId}
              claim={`${clientName} · ${fact.what}`}
            />
          </div>
        </Card>
      ))}
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
                <Card role="article" className={styles.card} key={fact.id}>
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
                </Card>
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
  // Quoted wording is one literal term, including conversational words.
  const phrases: string[] = [];
  const keywords = query.replace(
    /"([^"\n]+)"|“([^”\n]+)”/gu,
    (_, straight, curly) => {
      const phrase = String(straight ?? curly)
        .trim()
        .replace(/\s+/gu, " ");
      if (phrase) phrases.push(`"${phrase.toLowerCase()}"`);
      return " ";
    },
  );
  return [
    ...new Set([
      ...phrases,
      ...(
        keywords
          // Keep dotted country abbreviations intact before splitting punctuation.
          .replace(
            /(?<![\p{L}\p{N}.])u\.([sk])\.?(?![\p{L}\p{N}.])/giu,
            (_, country: string) => `U${country.toUpperCase()}`,
          )
          // Accept spaces before percent signs without losing the unit.
          .replace(/(\p{N})\s+%/gu, "$1%")
          // An omitted leading zero must not turn .5% into 5%.
          .replace(
            /(?<![\p{L}\p{N}.+−-])([+−-]?)\.(?=\p{N})/gu,
            (_, sign: string) => `${sign}0.`,
          )
          // Keep note references, ISO dates, and financial amounts intact.
          .match(
            /[Nn]-\d+|\d{4}-\d{2}-\d{2}|[+−-]?(?:\p{N}{1,3}(?:,\p{N}{3})+|\p{N}+)(?:\.\p{N}+)?(?:%|[\p{L}\p{N}]*)|[\p{L}\p{N}]+(?:\.\p{N}+[\p{L}\p{N}]*)?/gu,
          ) ?? []
      )
        .filter(
          (word) =>
            (word.length > 1 || /^\p{N}$/u.test(word)) &&
            // Preserve the region abbreviation, but still ignore conversational "us".
            (word === "US" || !STOPWORDS.has(word.toLowerCase())),
        )
        .map((word) =>
          word.toLowerCase().replaceAll(",", "").replaceAll("−", "-"),
        ),
    ]),
  ];
}

/** Count distinct terms without inventing phrases across separate fields. */
function matchScore(fields: string[], terms: string[]): number {
  return terms.filter((term) => {
    const pattern = new RegExp(termPattern(term), "iu");
    return fields.some((field) => pattern.test(field));
  }).length;
}

/** Keep short terms and amounts from matching inside unrelated words or numbers. */
function termPattern(term: string): string {
  if (term.startsWith('"') && term.endsWith('"')) {
    const wording = term.slice(1, -1);
    const phrase = wording
      .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
      .replace(/\s+/gu, "\\s+");
    // Exact wording must not start or end partway through a number.
    const start = /^[+−-]?\p{N}/u.test(wording)
      ? "(?<![\\p{L}\\p{N}.+−-]|\\p{N},)"
      : "(?<![\\p{L}\\p{N}])";
    const end = /\p{N}$/u.test(wording)
      ? "(?![\\p{L}\\p{N}]|[.,-]\\p{N})"
      : "(?![\\p{L}\\p{N}])";
    return `${start}${phrase}${end}`;
  }
  const literal = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  if (/^(?:n-\d+|\d{4}-\d{2}-\d{2})$/.test(term))
    return `(?<![\\p{L}\\p{N}-])${literal}(?![\\p{L}\\p{N}-])`;
  if (/^[+-]?\p{N}/u.test(term)) {
    const grouped = literal.replace(/\p{N}+/u, (integer) => {
      if (integer === "0" && term.includes(".")) return "0?";
      return integer.replace(/\B(?=(?:\p{N}{3})+$)/gu, ",");
    });
    const amount = (
      grouped === literal ? literal : `(?:${literal}|${grouped})`
    ).replaceAll("-", "[-−]");
    return `(?<![\\p{L}\\p{N}.+−-]|\\p{N},)${amount}(?![\\p{L}\\p{N}]|[.,-]\\p{N})`;
  }
  return term.length === 2
    ? `(?<![\\p{L}\\p{N}])${literal}(?![\\p{L}\\p{N}])`
    : literal;
}

/**
 * Keeps the retrieved records readable by marking the words that matched.
 * termPattern escapes decimal points while preserving the source wording.
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
function retrieve<T>(items: T[], terms: string[], text: (item: T) => string[]) {
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
  const noteText = (note: (typeof notes)[number]) => [
    String(note.record.note ?? note.title),
    String(note.record.channel ?? ""),
    String(note.record.note_date ?? ""),
    String(note.record.note_id ?? ""),
    String(note.record.rm_name ?? ""),
  ];

  const matchedNotes = retrieve(notes, terms, noteText);
  const matchedBeliefs = retrieve(preRead.beliefs, terms, (belief) => [
    belief.text,
    belief.note_id,
  ]);

  return (
    <div className={mergeClasses(styles.panel, styles.memory)}>
      <section className={styles.group} aria-label="Search the client memory">
        <Subtitle2 as="h3">Search RM notes</Subtitle2>
        <SearchBox
          className={styles.search}
          placeholder="Topic or exact phrase"
          aria-label="Search this client's RM notes"
          dismiss={{ "aria-label": "Clear note search" }}
          value={query}
          onChange={(_, data) => onQueryChange(data.value)}
          aria-describedby="memory-search-hint"
        />
        <Caption1 id="memory-search-hint">
          Use double quotes for an exact phrase.
        </Caption1>
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
        <Subtitle2 as="h3">Client statements</Subtitle2>
        {matchedBeliefs.length === 0 ? (
          <Body1 className={styles.empty}>
            {preRead.beliefs.length === 0
              ? "No extracted beliefs available."
              : `No recorded belief mentions ${terms.join(" or ")}.`}
          </Body1>
        ) : (
          <div className={styles.cards}>
            {matchedBeliefs.map((belief) => (
              <Card role="article" className={styles.card} key={belief.id}>
                <Body1>
                  “<Highlight text={belief.text} terms={terms} />”
                </Body1>
                <Caption1>
                  Note <Highlight text={belief.note_id} terms={terms} />
                </Caption1>
                <div className={styles.action}>
                  <WhyButton
                    citations={belief.citations}
                    clientId={preRead.client_id}
                    claim={`${preRead.name} · Extracted belief: “${belief.text}”`}
                  />
                </div>
              </Card>
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
                {note.record.note_id && (
                  <>
                    <Highlight
                      text={String(note.record.note_id)}
                      terms={terms}
                    />
                    {" · "}
                  </>
                )}
                <Highlight text={String(note.record.note_date)} terms={terms} />{" "}
                ·{" "}
                <Highlight
                  text={String(note.record.channel ?? "Note")}
                  terms={terms}
                />{" "}
                ·{" "}
                <Highlight
                  text={String(note.record.rm_name ?? "RM")}
                  terms={terms}
                />
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
