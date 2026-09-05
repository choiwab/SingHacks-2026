import {
  Badge,
  Body1,
  Body1Strong,
  Caption1,
  MessageBar,
  MessageBarBody,
  Subtitle2,
  Title2,
  makeStyles,
  mergeClasses,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { useLocation, useNavigate } from "react-router-dom";

import { CompactCalendar, briefState } from "./ClientDashboard";
import { DonutChart } from "./charts";
import type { MondayBriefProjection, RankedClient } from "./contracts";
import { FEATURED_PERSONAS } from "./demo/personas";
import type { Authorship } from "./evidence";
import { Eyebrow, useSurfaceStyles } from "./shared";

import { URGENCY } from "./presentation";

const BRIEF_COLOR = {
  Ready: "success" as const,
  "Needs review": "warning" as const,
  "Not prepared": "subtle" as const,
};

/** How many ranked clients the home screen shows before deferring to the switcher. */
const QUEUE_SIZE = 5;

const useStyles = makeStyles({
  header: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalXL,
    borderBottomWidth: tokens.strokeWidthThin,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.colorNeutralStroke2,
  },
  display: {
    fontSize: tokens.fontSizeHero800,
    lineHeight: tokens.lineHeightHero800,
    fontWeight: 300,
    letterSpacing: "-0.01em",
  },
  muted: { color: tokens.colorNeutralForeground3 },
  section: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalM,
    paddingTop: tokens.spacingVerticalXXL,
  },
  sectionHead: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
  },
  queue: {
    display: "flex",
    flexDirection: "column",
    listStyleType: "none",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
  },
  heroItem: {
    marginBottom: tokens.spacingVerticalL,
  },
  hero: {
    width: "100%",
    rowGap: tokens.spacingVerticalS,
    ...shorthands.padding(tokens.spacingVerticalXL, tokens.spacingHorizontalXL),
  },
  heroTop: {
    display: "flex",
    width: "100%",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalM,
    flexWrap: "wrap",
  },
  heroName: {
    fontWeight: 400,
  },
  heroOpen: {
    color: tokens.colorBrandForeground1,
    fontWeight: 500,
  },
  reason: {
    color: tokens.colorNeutralForeground2,
    maxWidth: "65ch",
  },
  row: {
    display: "flex",
    width: "100%",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
    alignItems: "stretch",
    ...shorthands.border("none"),
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingBlock: tokens.spacingVerticalM,
    paddingInline: 0,
    backgroundColor: "transparent",
    cursor: "pointer",
    textAlign: "start",
    transitionProperty: "background-color",
    transitionDuration: "180ms",
    transitionTimingFunction: "ease",
    ":hover": { backgroundColor: tokens.colorNeutralBackground2 },
  },
  rowTop: {
    display: "flex",
    width: "100%",
    alignItems: "baseline",
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalXXS,
    flexWrap: "wrap",
  },
  rowMeeting: {
    marginInlineStart: "auto",
  },
  rank: {
    color: tokens.colorNeutralForeground3,
    fontVariantNumeric: "tabular-nums",
    minWidth: "6.5rem",
  },
  badges: {
    display: "flex",
    flexWrap: "wrap",
    columnGap: tokens.spacingHorizontalXS,
    rowGap: tokens.spacingVerticalXS,
  },
  personaPair: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(22rem, 100%), 1fr))",
    gap: tokens.spacingHorizontalL,
  },
  personaCard: {
    rowGap: tokens.spacingVerticalM,
    ...shorthands.padding(tokens.spacingVerticalL, tokens.spacingHorizontalXL),
  },
  personaName: {
    display: "block",
    fontWeight: 400,
    fontSize: tokens.fontSizeBase500,
    lineHeight: tokens.lineHeightBase500,
    marginTop: tokens.spacingVerticalXXS,
  },
  personaDetail: {
    display: "block",
    color: tokens.colorNeutralForeground3,
  },
  personaHook: {
    color: tokens.colorNeutralForeground2,
    maxWidth: "48ch",
  },
  personaOpen: {
    color: tokens.colorBrandForeground1,
    fontWeight: 500,
    alignSelf: "flex-start",
    cursor: "pointer",
    ...shorthands.border("none"),
    backgroundColor: "transparent",
    ...shorthands.padding(0),
  },
});

function HeroCard({
  client,
  brief,
  open,
}: {
  client: RankedClient;
  brief: keyof typeof BRIEF_COLOR;
  open: () => void;
}) {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();
  const urgency = URGENCY[client.urgency];

  return (
    <li className={styles.heroItem}>
      <button
        type="button"
        className={mergeClasses(
          surfaces.surface,
          surfaces.interactive,
          styles.hero,
        )}
        onClick={open}
      >
        <span className={styles.heroTop}>
          <Eyebrow>Next priority</Eyebrow>
          <Caption1 className={styles.rank}>
            #1 · score {client.score.toFixed(0)}
          </Caption1>
        </span>
        <Title2 as="span" className={styles.heroName}>
          {client.name}
        </Title2>
        <Caption1>{client.meeting ?? "No meeting booked"}</Caption1>
        <Body1 className={styles.reason}>{client.reason}</Body1>
        <span className={styles.badges}>
          <Badge appearance="filled" color={urgency.color} size="small">
            {urgency.label}
          </Badge>
          <Badge appearance="tint" color={BRIEF_COLOR[brief]} size="small">
            {brief}
          </Badge>
        </span>
        <Body1 as="span" className={styles.heroOpen}>
          Open brief →
        </Body1>
      </button>
    </li>
  );
}

function QueueRow({
  client,
  rank,
  brief,
  open,
}: {
  client: RankedClient;
  rank: number;
  brief: keyof typeof BRIEF_COLOR;
  open: () => void;
}) {
  const styles = useStyles();
  const urgency = URGENCY[client.urgency];

  return (
    <li>
      <button type="button" className={styles.row} onClick={open}>
        <span className={styles.rowTop}>
          <Caption1 className={styles.rank}>
            #{rank + 1} · score {client.score.toFixed(0)}
          </Caption1>
          <Body1Strong>{client.name}</Body1Strong>
          <span className={styles.badges}>
            <Badge appearance="filled" color={urgency.color} size="small">
              {urgency.label}
            </Badge>
            <Badge appearance="tint" color={BRIEF_COLOR[brief]} size="small">
              {brief}
            </Badge>
          </span>
          <Caption1 className={styles.rowMeeting}>
            {client.meeting ?? "No meeting booked"}
          </Caption1>
        </span>
        <Body1 className={styles.reason}>{client.reason}</Body1>
      </button>
    </li>
  );
}

/**
 * The two featured contrast personas side by side: aggressive growth against
 * conservative income, each with its allocation donut. Demo overlay data; the
 * cards link into the same pre-reads.
 */
function PersonaStrip({
  projection,
  open,
}: {
  projection: MondayBriefProjection;
  open: (clientId: string) => void;
}) {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();

  return (
    <div className={styles.section}>
      <div className={styles.sectionHead}>
        <Subtitle2 as="h2" id="persona-title">
          Two mandates, two lives
        </Subtitle2>
        <Caption1 className={styles.muted}>
          Aggressive growth against conservative income
        </Caption1>
      </div>
      <div className={styles.personaPair} aria-labelledby="persona-title">
        {FEATURED_PERSONAS.map((persona) => {
          const name =
            projection.pre_reads[persona.clientId]?.name ?? persona.clientId;
          return (
            <article
              key={persona.clientId}
              className={mergeClasses(surfaces.surface, styles.personaCard)}
            >
              <div>
                <Eyebrow>{persona.stance}</Eyebrow>
                <Body1Strong as="h3" className={styles.personaName}>
                  {name}
                </Body1Strong>
                <Caption1 className={styles.personaDetail}>
                  {persona.stanceDetail}
                </Caption1>
              </div>
              <DonutChart
                size={124}
                slices={persona.allocation}
                centerValue={persona.totalDisplay}
                title={`${name} allocation: ${persona.allocation
                  .map((slice) => `${slice.label} ${slice.pct}%`)
                  .join(", ")}`}
              />
              <Body1 className={styles.personaHook}>{persona.hook}</Body1>
              <button
                type="button"
                className={styles.personaOpen}
                onClick={() => open(persona.clientId)}
              >
                Open brief →
              </button>
            </article>
          );
        })}
      </div>
    </div>
  );
}

/**
 * The RM's home screen (PRD 5. "the first screen is clearly an RM dashboard,
 * not a calendar product"): a ranked queue of who to prepare for next, with the
 * compact calendar as a supporting strip rather than the main product. The top
 * client is the hero; the rest of the queue reads as an index.
 */
export function Home({
  projection,
  reviews,
}: {
  projection: MondayBriefProjection;
  reviews: Record<string, Authorship>;
}) {
  const styles = useStyles();
  const navigate = useNavigate();
  const routeState = useLocation().state as { notice?: string } | null;

  const states = projection.ranking.map((client) =>
    briefState(
      Boolean(projection.pre_reads[client.client_id]),
      reviews[client.client_id] ?? "Unreviewed",
    ),
  );
  // Readiness is reported for the week's booked meetings, which is what the RM
  // has to walk into; the rest of the ranking is a call list, not a brief queue.
  const booked = projection.ranking
    .map((client, index) => ({ client, state: states[index] }))
    .filter((row) => row.client.meeting);
  const ready = booked.filter((row) => row.state === "Ready").length;
  const queue = projection.ranking.slice(0, QUEUE_SIZE);

  return (
    <section className="screen" aria-labelledby="home-title">
      {routeState?.notice && (
        <MessageBar intent="warning" role="status">
          <MessageBarBody>{routeState.notice}</MessageBarBody>
        </MessageBar>
      )}

      <header className={styles.header}>
        <Eyebrow>Monday brief</Eyebrow>
        <h1 id="home-title" className={styles.display}>
          Who needs you this week
        </h1>
        <Body1>
          {ready} of {booked.length} meeting{" "}
          {booked.length === 1 ? "brief" : "briefs"} ready
        </Body1>
        <Caption1 className={styles.muted}>
          Ranked by {projection.ranking_formula}
        </Caption1>
      </header>

      <div className={styles.section}>
        <CompactCalendar
          projection={projection}
          reviews={reviews}
          selectedClient=""
        />
      </div>

      <PersonaStrip
        projection={projection}
        open={(clientId) => navigate(`/clients/${clientId}/pre-read`)}
      />

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <Subtitle2 as="h2" id="queue-title">
            Priority queue
          </Subtitle2>
          <Caption1 className={styles.muted}>
            Top {queue.length} of {projection.ranking.length} clients
          </Caption1>
        </div>
        <ul className={styles.queue} aria-labelledby="queue-title">
          {queue.map((client, index) =>
            index === 0 ? (
              <HeroCard
                key={client.client_id}
                client={client}
                brief={states[index]}
                open={() => navigate(`/clients/${client.client_id}/pre-read`)}
              />
            ) : (
              <QueueRow
                key={client.client_id}
                client={client}
                rank={index}
                brief={states[index]}
                open={() => navigate(`/clients/${client.client_id}/pre-read`)}
              />
            ),
          )}
        </ul>
      </div>
    </section>
  );
}
