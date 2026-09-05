import {
  Body1,
  Caption1,
  Subtitle2,
  makeStyles,
  mergeClasses,
  shorthands,
  tokens,
} from "@fluentui/react-components";

import { DeltaBars, DonutChart } from "./charts";
import type { Persona } from "./demo/personas";
import { Eyebrow, WhyButton, useSurfaceStyles } from "./shared";

const useStyles = makeStyles({
  band: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(min(22rem, 100%), 1fr))",
    gap: tokens.spacingHorizontalL,
    paddingBlockEnd: tokens.spacingVerticalXXL,
    borderBottomWidth: "2px",
    borderBottomStyle: "solid",
    borderBottomColor: tokens.colorNeutralStroke2,
  },
  panel: {
    rowGap: tokens.spacingVerticalM,
  },
  head: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    columnGap: tokens.spacingHorizontalM,
  },
  events: {
    display: "flex",
    flexDirection: "column",
    margin: 0,
    padding: 0,
    listStyleType: "none",
  },
  event: {
    display: "grid",
    gridTemplateColumns: "minmax(0, 1fr)",
    gap: tokens.spacingHorizontalL,
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    paddingBlock: tokens.spacingVerticalM,
    "@container main (min-width: 48rem)": {
      gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
    },
  },
  eventCell: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXXS,
  },
  nextStep: {
    color: tokens.colorBrandForeground1,
  },
  chips: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    gap: tokens.spacingHorizontalS,
    paddingBlock: tokens.spacingVerticalM,
  },
  chip: {
    cursor: "pointer",
    ...shorthands.border("1px", "solid", tokens.colorNeutralStroke1),
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase200,
    paddingBlock: tokens.spacingVerticalXXS,
    paddingInline: tokens.spacingHorizontalM,
    transitionProperty: "border-color, background-color",
    transitionDuration: "180ms",
    transitionTimingFunction: "ease",
    ":hover": {
      ...shorthands.borderColor(tokens.colorBrandStroke1),
      backgroundColor: tokens.colorBrandBackground2,
    },
  },
});

/**
 * Persona portfolio band: allocation donut and change-since-last-snapshot
 * bars, each tied back to the fixture's holdings rows via "Why?".
 */
export function PortfolioBand({ persona }: { persona: Persona }) {
  const styles = useStyles();
  const surfaces = useSurfaceStyles();

  return (
    <section className={styles.band} aria-label="Portfolio">
      <div className={mergeClasses(surfaces.surface, styles.panel)}>
        <div className={styles.head}>
          <Subtitle2 as="h2">Allocation</Subtitle2>
          <Eyebrow>{persona.stance}</Eyebrow>
        </div>
        <DonutChart
          slices={persona.allocation}
          centerValue={persona.totalDisplay}
          title={`Allocation: ${persona.allocation
            .map((slice) => `${slice.label} ${slice.pct}%`)
            .join(", ")}`}
        />
        <WhyButton
          citations={persona.allocation.flatMap((slice) => slice.citations)}
          clientId={persona.clientId}
          claim={`Allocation as of the latest snapshot: ${persona.allocation
            .map((slice) => `${slice.label} ${slice.pct}%`)
            .join(", ")}.`}
        >
          Why this allocation?
        </WhyButton>
      </div>
      <div className={mergeClasses(surfaces.surface, styles.panel)}>
        <div className={styles.head}>
          <Subtitle2 as="h2">Since last snapshot</Subtitle2>
          <Eyebrow>2025-12-31 to 2026-08-26</Eyebrow>
        </div>
        <DeltaBars
          items={persona.performance}
          title={`Change since last snapshot: ${persona.performance
            .map((item) => `${item.label} ${item.display}`)
            .join(", ")}`}
        />
        <WhyButton
          citations={persona.performance.flatMap((item) => item.citations)}
          clientId={persona.clientId}
          claim={`Change since the 2025-12-31 snapshot: ${persona.performance
            .map((item) => `${item.label} ${item.display}`)
            .join(", ")}.`}
        >
          Why these changes?
        </WhyButton>
      </div>
    </section>
  );
}

/**
 * Lifestyle timeline: what happened in the client's life, and the conversation
 * to open next. This is where money meets client needs.
 */
export function LifeEvents({ persona }: { persona: Persona }) {
  const styles = useStyles();

  return (
    <ul className={styles.events}>
      {persona.lifeEvents.map((event) => (
        <li className={styles.event} key={event.happened}>
          <div className={styles.eventCell}>
            <Eyebrow>What happened</Eyebrow>
            <Body1>{event.happened}</Body1>
          </div>
          <div className={styles.eventCell}>
            <Eyebrow>Next step</Eyebrow>
            <Body1 className={styles.nextStep}>{event.nextStep}</Body1>
            <div>
              <WhyButton
                citations={event.citations}
                clientId={persona.clientId}
                claim={`${event.happened} Recommended next step: ${event.nextStep}`}
              />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

/**
 * AI key insights from meetings: keyword chips lifted from this client's RM
 * notes. Selecting one runs the Memory search on that term.
 */
export function KeywordChips({
  persona,
  onSelect,
}: {
  persona: Persona;
  onSelect: (keyword: string) => void;
}) {
  const styles = useStyles();

  return (
    <div className={styles.chips} role="group" aria-label="Key insights">
      <Eyebrow>Key insights</Eyebrow>
      {persona.keywords.map((keyword) => (
        <button
          key={keyword}
          type="button"
          className={styles.chip}
          onClick={() => onSelect(keyword)}
        >
          {keyword}
        </button>
      ))}
      <Caption1>
        From meetings and calls. Select one to search the notes.
      </Caption1>
    </div>
  );
}
