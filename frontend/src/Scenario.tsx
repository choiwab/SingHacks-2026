import {
  Body1,
  Caption1,
  Card,
  Link,
  mergeClasses,
  Subtitle2,
  Title2,
  Title3,
  makeStyles,
  ToggleButton,
  tokens,
} from "@fluentui/react-components";
import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import type { MondayBriefProjection, ScenarioKey } from "./contracts";
import { CitedList, WhyButton } from "./shared";

const useStyles = makeStyles({
  header: {
    display: "grid",
    gap: tokens.spacingVerticalL,
    paddingTop: tokens.spacingVerticalXL,
    paddingBottom: tokens.spacingVerticalXL,
  },
  copy: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: tokens.spacingVerticalS,
    minWidth: 0,
  },
  title: { maxWidth: "none", letterSpacing: "normal" },
  muted: { color: tokens.colorNeutralForeground3 },
  result: {
    display: "grid",
    gap: tokens.spacingHorizontalXXL,
    padding: tokens.spacingHorizontalXL,
    "@container main (min-width: 48rem)": {
      gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)",
      alignItems: "center",
    },
  },
  range: { margin: 0, fontVariantNumeric: "tabular-nums" },
  amount: { whiteSpace: "nowrap" },
  visual: { minWidth: 0, paddingBottom: tokens.spacingVerticalXS },
  disclaimer: {
    display: "block",
    marginTop: "2.2rem",
    color: tokens.colorNeutralForeground3,
  },
  detail: {
    display: "flex",
    flexDirection: "column",
    gap: tokens.spacingVerticalM,
    paddingTop: tokens.spacingVerticalXXL,
  },
  toggle: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: tokens.spacingHorizontalS,
  },
  option: {
    minHeight: "44px",
  },
});

function money(value: number, currency: string): string {
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${currency} ${Math.abs(value / 1_000_000).toFixed(1)}m`;
}

function percent(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

export function Scenario({
  projection,
}: {
  projection: MondayBriefProjection;
}) {
  const styles = useStyles();
  const { clientId = "" } = useParams();
  const navigate = useNavigate();
  const [scenarioKey, setScenarioKey] = useState<ScenarioKey>("reopens");
  const preRead = projection.pre_reads[clientId];
  const pair = projection.scenarios[clientId];

  if (!preRead || !pair) {
    return (
      <Navigate
        to="/"
        replace
        state={{
          notice: `Client ${clientId || "requested"} was not found. Showing the dashboard.`,
        }}
      />
    );
  }

  const scenario = pair[scenarioKey];
  const valueRange = `${money(scenario.low_delta, scenario.currency)} to ${money(scenario.high_delta, scenario.currency)}`;
  const percentRange = `${percent(scenario.low_pct)} to ${percent(scenario.high_pct)} of today's portfolio`;
  const disclaimer = scenario.disclaimer.replace(
    "Precomputed range, ",
    "Estimated range · ",
  );
  const resultSummary = `${preRead.name} · ${scenario.name}: ${valueRange} (${percentRange}). ${disclaimer}`;
  const scale = (value: number) =>
    Math.max(0, Math.min(100, ((value + 20) / 40) * 100));
  const left = scale(scenario.low_pct);
  const right = scale(scenario.high_pct);

  return (
    <section
      className="screen scenario-screen"
      aria-labelledby="scenario-title"
    >
      <div className="screen-kicker">
        <Link
          as="button"
          type="button"
          onClick={() => navigate(`/clients/${clientId}/pre-read`)}
        >
          ← Pre-read
        </Link>
        <p>
          <strong>Scenario rehearsal</strong>
        </p>
      </div>

      <header className={styles.header}>
        <div className={styles.copy}>
          <Caption1 className={styles.muted}>{preRead.name}</Caption1>
          <Title3 as="h1" id="scenario-title" className={styles.title}>
            Rehearse the Strait conversation
          </Title3>
        </div>
        <div className={styles.toggle} role="group" aria-label="Scenario">
          <ToggleButton
            className={styles.option}
            appearance={scenarioKey === "reopens" ? "primary" : "secondary"}
            checked={scenarioKey === "reopens"}
            onClick={() => setScenarioKey("reopens")}
          >
            Strait reopens
          </ToggleButton>
          <ToggleButton
            className={styles.option}
            appearance={scenarioKey === "escalates" ? "primary" : "secondary"}
            checked={scenarioKey === "escalates"}
            onClick={() => setScenarioKey("escalates")}
          >
            Strait escalates
          </ToggleButton>
        </div>
      </header>

      <p className="scenario-announcement" role="status" aria-atomic="true">
        {resultSummary}
      </p>

      <Card
        role="region"
        className={styles.result}
        aria-labelledby="scenario-name"
      >
        <div className={styles.copy}>
          <Subtitle2 as="h2" className="scenario-label" id="scenario-name">
            {scenario.name}
          </Subtitle2>
          <Title2 as="p" className={mergeClasses("range-value", styles.range)}>
            <span className={styles.amount}>
              {money(scenario.low_delta, scenario.currency)}
            </span>{" "}
            to{" "}
            <span className={styles.amount}>
              {money(scenario.high_delta, scenario.currency)}
            </span>
          </Title2>
          <Body1 className={mergeClasses("range-percent", styles.muted)}>
            {percentRange}
          </Body1>
          <WhyButton
            citations={scenario.citations}
            clientId={clientId}
            claim={resultSummary}
            children="Why this range?"
          />
        </div>
        <div className={styles.visual}>
          <div
            className="range-axis"
            role="img"
            aria-label={`${scenario.name}: ${percentRange}. ${disclaimer} Scale: −20% to +20%.`}
          >
            <span className="axis-start">−20%</span>
            <span className="axis-zero">0</span>
            <span className="axis-end">+20%</span>
            <i className="zero-line" />
            <i
              className="range-line"
              style={{
                left: `${left}%`,
                width: `${Math.max(right - left, 1.5)}%`,
              }}
            />
          </div>
          <Caption1 className={styles.disclaimer}>{disclaimer}</Caption1>
        </div>
      </Card>

      <section
        className={styles.detail}
        aria-labelledby="scenario-detail-title"
      >
        <Subtitle2 as="h2" id="scenario-detail-title">
          What changes
        </Subtitle2>
        <CitedList
          items={scenario.bullets}
          clientId={clientId}
          evidenceContext={`${preRead.name} · ${scenario.name}. ${disclaimer}`}
        />
      </section>
    </section>
  );
}
