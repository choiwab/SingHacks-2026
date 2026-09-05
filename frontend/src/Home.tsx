import {
  Badge,
  Body1,
  Body1Strong,
  Caption1,
  MessageBar,
  MessageBarBody,
  Subtitle2,
  Title3,
  makeStyles,
  shorthands,
  tokens,
} from "@fluentui/react-components";
import { useLocation, useNavigate } from "react-router-dom";

import { CompactCalendar, briefState } from "./ClientDashboard";
import type { MondayBriefProjection, RankedClient } from "./contracts";
import type { Authorship } from "./evidence";

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
    rowGap: tokens.spacingVerticalXS,
    paddingBottom: tokens.spacingVerticalXL,
    borderBottomWidth: tokens.strokeWidthThin,
    borderBottomStyle: "solid",
    borderBottomColor: tokens.colorNeutralStroke2,
  },
  eyebrow: { color: tokens.colorNeutralForeground3 },
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
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(17rem, 1fr))",
    columnGap: tokens.spacingHorizontalL,
    rowGap: tokens.spacingVerticalL,
    listStyleType: "none",
    ...shorthands.margin(0),
    ...shorthands.padding(0),
  },
  card: {
    display: "flex",
    width: "100%",
    height: "100%",
    flexDirection: "column",
    alignItems: "flex-start",
    rowGap: tokens.spacingVerticalXS,
    ...shorthands.padding(tokens.spacingVerticalM, tokens.spacingHorizontalM),
    ...shorthands.border(tokens.strokeWidthThin, "solid"),
    ...shorthands.borderColor(tokens.colorNeutralStroke2),
    ...shorthands.borderRadius(tokens.borderRadiusMedium),
    backgroundColor: tokens.colorNeutralBackground1,
    cursor: "pointer",
    textAlign: "start",
    ":hover": { backgroundColor: tokens.colorNeutralBackground1Hover },
  },
  cardTop: {
    display: "flex",
    width: "100%",
    alignItems: "center",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalS,
  },
  rank: {
    color: tokens.colorNeutralForeground3,
    fontVariantNumeric: "tabular-nums",
  },
  reason: { color: tokens.colorNeutralForeground2 },
  badges: {
    display: "flex",
    flexWrap: "wrap",
    columnGap: tokens.spacingHorizontalXS,
    rowGap: tokens.spacingVerticalXS,
    paddingTop: tokens.spacingVerticalXS,
  },
});

function QueueCard({
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
      <button type="button" className={styles.card} onClick={open}>
        <span className={styles.cardTop}>
          <Caption1 className={styles.rank}>
            #{rank + 1} · score {client.score.toFixed(0)}
          </Caption1>
          <Badge appearance="filled" color={urgency.color} size="small">
            {urgency.label}
          </Badge>
        </span>
        <Body1Strong>{client.name}</Body1Strong>
        <Caption1>{client.meeting ?? "No meeting booked"}</Caption1>
        <Body1 className={styles.reason}>{client.reason}</Body1>
        <span className={styles.badges}>
          <Badge appearance="tint" color={BRIEF_COLOR[brief]} size="small">
            {brief}
          </Badge>
        </span>
      </button>
    </li>
  );
}

/**
 * The RM's home screen (PRD 5. "the first screen is clearly an RM dashboard,
 * not a calendar product"): a ranked queue of who to prepare for next, with the
 * compact calendar as a supporting strip rather than the main product.
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
        <Caption1 className={styles.eyebrow}>RM dashboard</Caption1>
        <Title3 as="h1" id="home-title">
          Who needs you this week
        </Title3>
        <Body1>
          {booked.length === 1 ? "1 meeting" : `${booked.length} meetings`} this
          week · {ready} of {booked.length}{" "}
          {booked.length === 1 ? "brief" : "briefs"} ready. Data as of{" "}
          {projection.as_of}.
        </Body1>
        <Caption1 className={styles.eyebrow}>
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

      <div className={styles.section}>
        <div className={styles.sectionHead}>
          <Subtitle2 as="h2" id="queue-title">
            Priority queue
          </Subtitle2>
          <Caption1 className={styles.eyebrow}>
            Top {queue.length} of {projection.ranking.length}. The rest are in
            the switcher.
          </Caption1>
        </div>
        <ul className={styles.queue} aria-labelledby="queue-title">
          {queue.map((client, index) => (
            <QueueCard
              key={client.client_id}
              client={client}
              rank={index}
              brief={states[index]}
              open={() => navigate(`/clients/${client.client_id}/pre-read`)}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}
