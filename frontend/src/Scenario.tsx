import { useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import type { MondayBriefProjection, ScenarioKey } from "./contracts";
import { CitedList, WhyButton } from "./shared";

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
          notice: `Client ${clientId || "requested"} was not found. Showing the Monday list.`,
        }}
      />
    );
  }

  const scenario = pair[scenarioKey];
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
        <button
          className="back-link"
          type="button"
          onClick={() => navigate(`/clients/${clientId}/pre-read`)}
        >
          ← Pre-read
        </button>
        <p>
          <span>Feature 02</span> Evidence-backed Scenario Rehearsal
        </p>
      </div>

      <header className="scenario-heading">
        <div>
          <p className="eyebrow accent">Precomputed · {preRead.name}</p>
          <h1 id="scenario-title">Rehearse the Strait conversation.</h1>
        </div>
        <div className="scenario-toggle" role="group" aria-label="Scenario">
          <button
            type="button"
            aria-pressed={scenarioKey === "reopens"}
            onClick={() => setScenarioKey("reopens")}
          >
            Strait reopens
          </button>
          <button
            type="button"
            aria-pressed={scenarioKey === "escalates"}
            onClick={() => setScenarioKey("escalates")}
          >
            Strait escalates
          </button>
        </div>
      </header>

      <section className="scenario-result" aria-labelledby="scenario-name">
        <div className="range-copy">
          <p className="scenario-label" id="scenario-name">
            {scenario.name}
          </p>
          <p className="range-value">
            {money(scenario.low_delta, scenario.currency)} to{" "}
            {money(scenario.high_delta, scenario.currency)}
          </p>
          <p className="range-percent">
            {percent(scenario.low_pct)} to {percent(scenario.high_pct)} of
            today&apos;s portfolio
          </p>
          <WhyButton
            citations={scenario.citations}
            clientId={clientId}
            children="Why this range?"
          />
        </div>
        <div className="range-visual">
          <div
            className="range-axis"
            aria-label="Estimated portfolio change range from negative twenty to positive twenty percent"
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
          <p>
            {scenario.disclaimer.replace(
              "Precomputed range, ",
              "Estimated range · ",
            )}
          </p>
        </div>
      </section>

      <section
        className="scenario-detail"
        aria-labelledby="scenario-detail-title"
      >
        <div className="block-heading">
          <p>Talk through</p>
          <h2 id="scenario-detail-title">What changes</h2>
        </div>
        <CitedList
          items={scenario.bullets}
          clientId={clientId}
          className="scenario-bullets"
        />
      </section>
    </section>
  );
}
