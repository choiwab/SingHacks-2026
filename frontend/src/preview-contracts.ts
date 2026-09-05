/**
 * Frozen UI preview model for the historical Monday Brief fixture.
 * These handwritten types describe preview data, not the live backend API.
 * ADR 0002 removed the projection endpoint; the future DemoViewModel contract
 * must come from the backend when that integration is available.
 * Existing consumer names are retained to preserve the frontend components.
 */

interface Evidence {
  id: string;
  kind: string;
  title: string;
  source: string;
  record: Record<string, unknown>;
}

interface FactBase {
  id: string;
  what: string;
  source_rows: string[];
  event_ids: string[];
  confidence: "high" | "medium" | "low";
}

type Fact = FactBase &
  (
    | {
        kind: "profile";
        numbers: {
          name: string;
          currency: string;
          language: string;
          residence: string;
          booking_centre: string;
          risk_tolerance_score: number;
          life_stage: string;
        };
      }
    | {
        kind: "change";
        numbers: {
          instrument: string;
          delta: number;
          currency: string;
        };
      }
    | {
        kind: "mandate_gap";
        numbers: {
          asset_class: string;
          actual_pct: number;
          limit_pct: number;
          boundary: "minimum" | "maximum";
          gap_pct: number;
          scope: string;
        };
      }
    | {
        kind: "deadline";
        numbers: {
          days: number;
          amount: number;
          currency: string | null;
          daily_liquid?: number | null;
          amount_in_portfolio_currency?: number | null;
          portfolio_currency?: string | null;
          coverage_pct?: number | null;
          description?: string | null;
        };
      }
    | {
        kind: "facility";
        numbers: {
          ltv_pct: number;
          trigger_pct: number;
          gap_pct: number;
        };
      }
    | {
        kind: "concentration";
        numbers: {
          weight_pct: number;
          value: number;
        };
      }
  );

export interface CitedText {
  text: string;
  citations: string[];
}

interface Belief extends CitedText {
  id: string;
  note_id: string;
}

interface Gap {
  id: string;
  belief: string;
  data: string;
  citations: string[];
}

export interface WorkflowContext {
  system: string;
  status: string;
  citations: string[];
}

export interface ClientPreRead {
  client_id: string;
  name: string;
  language: string;
  what_changed: CitedText[];
  gap: Gap;
  rules_money: CitedText[];
  opening: CitedText;
  uncertainty: CitedText;
  beliefs: Belief[];
  workflow: WorkflowContext[];
}

export interface RankedClient {
  client_id: string;
  name: string;
  score: number;
  components: {
    gap: number;
    deadline: number;
    consequence: number;
  };
  meeting: string | null;
  meeting_source: string | null;
  reason: string;
  urgency: "now" | "soon" | "watch";
  citations: string[];
}

interface ScenarioBullet extends CitedText {
  low_delta: number;
  high_delta: number;
}

interface Scenario {
  name: string;
  currency: string;
  portfolio_value: number;
  low_delta: number;
  high_delta: number;
  low_pct: number;
  high_pct: number;
  bullets: ScenarioBullet[];
  citations: string[];
  disclaimer: string;
}

export interface ScenarioPair {
  reopens: Scenario;
  escalates: Scenario;
}

export interface MondayBriefProjection {
  schema_version: 1;
  as_of: string;
  pipeline: string[];
  ranking_formula: string;
  ranking: RankedClient[];
  facts: Record<string, Fact[]>;
  pre_reads: Record<string, ClientPreRead>;
  scenarios: Record<string, ScenarioPair>;
  evidence: Record<string, Evidence>;
}
