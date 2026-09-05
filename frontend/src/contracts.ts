import type { components } from "./generated/openapi";

type Schemas = components["schemas"];

// Live API contracts remain generated. The removed projection endpoint is not
// part of this schema and must not be added back just to type the retained UI.
export type ReviewRequest = Schemas["ReviewRequest"];
export type ReviewResponse = Schemas["ReviewResponse"];
export type ReviewAction = ReviewRequest["action"];
export type CitationId = string;

// Transitional frontend view model for the retained screens and their fixtures.
// Replace at the new dashboard API integration boundary, not in generated code.
export interface CitedText {
  text: string;
  citations: CitationId[];
}

export interface WorkflowContext {
  system: string;
  status: string;
  citations: CitationId[];
}

export interface RankedClient {
  client_id: string;
  name: string;
  score: number;
  components: { gap: number; deadline: number; consequence: number };
  meeting: string | null;
  meeting_source: string | null;
  reason: string;
  urgency: "now" | "soon" | "watch";
  citations: CitationId[];
}

export interface ClientPreRead {
  client_id: string;
  name: string;
  language: string;
  what_changed: CitedText[];
  gap: {
    id: string;
    belief: string;
    data: string;
    citations: CitationId[];
  };
  rules_money: CitedText[];
  opening: CitedText;
  uncertainty: CitedText;
  beliefs: (CitedText & { id: string; note_id: string })[];
  workflow: WorkflowContext[];
}

interface Scenario {
  name: string;
  currency: string;
  portfolio_value: number;
  low_delta: number;
  high_delta: number;
  low_pct: number;
  high_pct: number;
  bullets: (CitedText & { low_delta: number; high_delta: number })[];
  citations: CitationId[];
  disclaimer: string;
}

export interface ScenarioPair {
  reopens: Scenario;
  escalates: Scenario;
}

export type ScenarioKey = keyof ScenarioPair;

type FactNumbers = {
  profile: {
    name: string;
    currency: string;
    language: string;
    residence: string;
    booking_centre: string;
    risk_tolerance_score: number;
    life_stage: string;
  };
  change: { instrument: string; delta: number; currency: string };
  mandate_gap: {
    asset_class: string;
    actual_pct: number;
    limit_pct: number;
    boundary: "minimum" | "maximum";
    gap_pct: number;
    scope: string;
  };
  deadline: {
    days: number;
    amount: number;
    currency: string | null;
    daily_liquid?: number | null;
    amount_in_portfolio_currency?: number | null;
    portfolio_currency?: string | null;
    coverage_pct?: number | null;
    description?: string | null;
  };
  facility: { ltv_pct: number; trigger_pct: number; gap_pct: number };
  concentration: { weight_pct: number; value: number };
};

export type ProjectionFact = {
  [Kind in keyof FactNumbers]: {
    id: string;
    kind: Kind;
    what: string;
    numbers: FactNumbers[Kind];
    source_rows: CitationId[];
    event_ids: CitationId[];
    confidence: "high" | "medium" | "low";
  };
}[keyof FactNumbers];

export interface MondayBriefProjection {
  schema_version: 1;
  as_of: string;
  pipeline: string[];
  ranking_formula: string;
  ranking: RankedClient[];
  pre_reads: Record<string, ClientPreRead>;
  scenarios: Record<string, ScenarioPair>;
  facts: Record<string, ProjectionFact[]>;
  evidence: Record<
    CitationId,
    {
      id: string;
      kind: string;
      title: string;
      source: string;
      record: Record<string, unknown>;
    }
  >;
}
