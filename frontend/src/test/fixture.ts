import type {
  ClientPreRead,
  MondayBriefProjection,
  ScenarioPair,
} from "../generated/api";

function preRead(clientId: string, name: string): ClientPreRead {
  return {
    client_id: clientId,
    name,
    beliefs: [
      {
        id: `${clientId}:belief:1`,
        note_id: "N-001",
        text: "Keep it safe.",
        citations: ["note:1"],
      },
    ],
    gap: {
      id: `${clientId}:gap:1`,
      belief: "Keep it safe.",
      data: "Equity is above the mandate limit.",
      citations: [`${clientId}:fact:gap`],
    },
    language: "English",
    opening: {
      text: "May I show you the gap?",
      citations: [`${clientId}:fact:gap`],
    },
    rules_money: [
      {
        text: "Equity is above the maximum.",
        citations: [`${clientId}:fact:gap`],
      },
    ],
    uncertainty: {
      text: "Confirm intent before advising.",
      citations: [`${clientId}:fact:gap`],
    },
    what_changed: [
      { text: "Equity increased.", citations: [`${clientId}:fact:gap`] },
    ],
    workflow: [
      { system: "CRM", status: "Email logged", citations: ["note:1"] },
    ],
  };
}

function scenarios(currency: string): ScenarioPair {
  const base = {
    currency,
    portfolio_value: 10_000_000,
    disclaimer: "Precomputed range, not a forecast.",
    bullets: [
      {
        text: "Equities move first.",
        low_delta: -100_000,
        high_delta: 100_000,
        citations: ["event:1"],
      },
    ],
    citations: ["event:1"],
  };
  return {
    reopens: {
      ...base,
      name: "Strait reopens",
      low_delta: -100_000,
      high_delta: 300_000,
      low_pct: -1,
      high_pct: 3,
    },
    escalates: {
      ...base,
      name: "Strait escalates",
      low_delta: -800_000,
      high_delta: -200_000,
      low_pct: -8,
      high_pct: -2,
    },
  };
}

export const projectionFixture: MondayBriefProjection = {
  schema_version: 1,
  as_of: "2026-08-26",
  pipeline: "offline",
  ranking_formula: "0.4 gap + 0.35 deadline + 0.25 consequence",
  ranking: [
    {
      client_id: "CL-0003",
      name: "Margarethe Voss-Brenner",
      score: 95,
      urgency: "now",
      reason: "Equity is above the mandate limit.",
      meeting: "Mon 10:30",
      meeting_source: "Calendar preview",
      components: { gap: 95 },
      citations: ["CL-0003:fact:gap"],
    },
    {
      client_id: "CL-0019",
      name: "Abdullah Al-Nuaimi",
      score: 90,
      urgency: "soon",
      reason: "Shipping conditions affect the portfolio.",
      meeting: null,
      meeting_source: null,
      components: { gap: 90 },
      citations: ["CL-0019:fact:gap"],
    },
  ],
  pre_reads: {
    "CL-0003": preRead("CL-0003", "Margarethe Voss-Brenner"),
    "CL-0019": preRead("CL-0019", "Abdullah Al-Nuaimi"),
  },
  scenarios: {
    "CL-0003": scenarios("EUR"),
    "CL-0019": scenarios("USD"),
  },
  facts: {
    "CL-0003": [
      {
        id: "CL-0003:fact:gap",
        kind: "mandate_gap",
        what: "Equity is above the mandate limit.",
        numbers: { actual_pct: 71.5 },
        source_rows: ["holding:1"],
        event_ids: ["event:1"],
        confidence: "high",
      },
    ],
    "CL-0019": [
      {
        id: "CL-0019:fact:gap",
        kind: "mandate_gap",
        what: "Shipping conditions affect the portfolio.",
        numbers: {},
        source_rows: ["holding:1"],
        event_ids: ["event:1"],
        confidence: "medium",
      },
    ],
  },
  evidence: {
    "holding:1": {
      id: "holding:1",
      kind: "Holding",
      title: "Current equity holding",
      source: "data/holdings.csv",
      record: { market_value_base: 7_150_000 },
    },
    "event:1": {
      id: "event:1",
      kind: "Event",
      title: "Strait shipping event",
      source: "data/event_log.csv",
      record: { event_date: "2026-08-05" },
    },
    "note:1": {
      id: "note:1",
      kind: "Note",
      title: "RM note",
      source: "data/rm_notes.json",
      record: { note: "Keep it safe." },
    },
  },
};
